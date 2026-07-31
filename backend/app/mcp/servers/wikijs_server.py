"""
WikiJSMCPServer — MCP Server pour Wiki.js (wiki open source self-hosted).

Wiki.js n'expose PAS d'API REST : tout passe par un endpoint GraphQL unique
`/graphql`. Doc officielle : https://docs.requarks.io/dev/api

Auth :
  - Header "Authorization: Bearer <TOKEN>"
  - Token généré côté Wiki.js : Administration > API Access > New API Key
  - Le token doit avoir les scopes nécessaires (read:pages, write:pages, manage:pages, ...)

Piège connu (cf. requarks/wiki#5910) :
  La mutation `pages.update` n'est PAS un patch partiel : Wiki.js réutilise le
  comportement du formulaire d'édition front-end. Si `content` (ou d'autres
  champs) est omis, le contenu peut être écrasé/vidé selon la version.
  => update_page() charge systématiquement la page existante et fusionne les
     champs non fournis AVANT d'envoyer la mutation, pour éviter toute perte
     de contenu.

Méthodes exposées :
  - list_pages
  - get_page (par id OU par path)
  - search_pages
  - create_page
  - update_page (merge-safe, cf. ci-dessus)
  - move_page
  - delete_page
  - get_page_tree
"""
import httpx
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class WikiJSMCPServer:
    """
    MCP Server pour Wiki.js.

    Config attendue dans mcp_config["wikijs"] :
    {
        "base_url": "https://wiki.mondomaine.fr",
        "token": "eyJhbGciOiJIUzI1NiIs...",
        "default_locale": "fr"          # optionnel, défaut "en"
    }
    """

    def __init__(self, base_url: str, token: str, default_locale: str = "en"):
        """
        Args:
            base_url: URL de l'instance Wiki.js, ex: https://wiki.mondomaine.fr
            token:    Token API Wiki.js (Administration > API Access)
            default_locale: Locale par défaut utilisée si non précisée en paramètre
        """
        self.wiki_url = base_url.rstrip("/")
        self.graphql_url = f"{self.wiki_url}/graphql"
        self.token = token
        self.default_locale = default_locale

        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        logger.info(f"WikiJS MCP Server initialized: {self.wiki_url}")

    # ─────────────────────────────────────────────────────────────────────────
    # Coeur GraphQL
    # ─────────────────────────────────────────────────────────────────────────

    async def _gql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Exécute une requête/mutation GraphQL et lève une exception si erreur.

        IMPORTANT : WikiJS (Apollo Server) répond en HTTP 400 pour les erreurs
        de validation GraphQL (champ/argument invalide), avec un body JSON
        exploitable (`errors[].message`). On lit donc TOUJOURS le body avant
        de considérer un raise_for_status, sinon le vrai message est perdu
        derrière une httpx.HTTPStatusError générique.
        """
        payload = {"query": query, "variables": variables or {}}

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            r = await client.post(self.graphql_url, headers=self.headers, json=payload)

            try:
                result = r.json()
            except ValueError:
                r.raise_for_status()
                raise

        if "errors" in result and result["errors"]:
            messages = "; ".join(e.get("message", str(e)) for e in result["errors"])
            logger.error(f"WikiJS GraphQL error (HTTP {r.status_code}): {messages}")
            raise Exception(f"WikiJS GraphQL error: {messages}")

        if r.status_code >= 400:
            raise Exception(f"WikiJS HTTP {r.status_code} with no GraphQL errors[]: {result}")

        return result.get("data", {})

    @staticmethod
    def _check_response_result(result: Dict[str, Any], action: str) -> None:
        """Vérifie le responseResult standard des mutations Wiki.js."""
        rr = result.get("responseResult") or {}
        if not rr.get("succeeded"):
            raise Exception(
                f"WikiJS {action} failed [{rr.get('slug')}]: {rr.get('message')}"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Lecture
    # ─────────────────────────────────────────────────────────────────────────

    async def list_pages(
        self,
        order_by: str = "TITLE",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Liste toutes les pages (id, path, title, description, updatedAt)."""
        query = """
        query ListPages($orderBy: PageOrderBy, $limit: Int) {
          pages {
            list(orderBy: $orderBy, limit: $limit) {
              id
              path
              title
              description
              locale
              isPublished
              updatedAt
              createdAt
            }
          }
        }
        """
        data = await self._gql(query, {"orderBy": order_by, "limit": limit})
        pages = data.get("pages", {}).get("list", [])
        logger.info(f"Retrieved {len(pages)} pages from WikiJS")
        return pages

    async def get_page(
        self,
        page_id: Optional[int] = None,
        path: Optional[str] = None,
        locale: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Récupère une page complète (contenu inclus), par id OU par path.
        Au moins un des deux doit être fourni.
        """
        locale = locale or self.default_locale

        if page_id is not None:
            query = """
            query GetPage($id: Int!) {
              pages {
                single(id: $id) {
                  id path title description content
                  contentType editor locale
                  isPublished isPrivate
                  tags { tag }
                  createdAt updatedAt
                  authorName authorId
                }
              }
            }
            """
            data = await self._gql(query, {"id": page_id})
            page = data.get("pages", {}).get("single")

        elif path is not None:
            # singleByPath nécessite généralement des droits admin sur le token
            query = """
            query GetPageByPath($path: String!, $locale: String!) {
              pages {
                singleByPath(path: $path, locale: $locale) {
                  id path title description content
                  contentType editor locale
                  isPublished isPrivate
                  tags { tag }
                  createdAt updatedAt
                  authorName authorId
                }
              }
            }
            """
            try:
                data = await self._gql(query, {"path": path.lstrip("/"), "locale": locale})
                page = data.get("pages", {}).get("singleByPath")
            except Exception as exc:
                # WikiJS lève "This page does not exist." au lieu de renvoyer null
                # pour un path inconnu (résolveur singleByPath). C'est un cas
                # normal (page pas encore créée), pas une vraie erreur : on le
                # traite comme "not found" pour que upsert_page() puisse
                # basculer en create_page() proprement.
                if "does not exist" in str(exc).lower():
                    logger.info(f"Page not found by path (normal for new pages): {path}")
                    return None
                raise

        else:
            raise ValueError("Provide either page_id or path")

        if page:
            # tags arrive en [PageTag]! (objets {tag, id, ...}) côté query GraphQL,
            # alors que create/update attendent [String]! en entrée : on aplatit ici
            # pour que get_page()["tags"] soit directement réutilisable partout ailleurs.
            page["tags"] = [t["tag"] for t in (page.get("tags") or [])]
            logger.info(f"Retrieved page: {page.get('path')} (id={page.get('id')})")
        else:
            logger.info(f"Page not found (id={page_id}, path={path})")

        return page

    async def search_pages(
        self,
        query_text: str,
        path: str = "",
        locale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Recherche plein texte sur titre/description/path.

        IMPORTANT : locale=None par défaut (pas de fallback sur default_locale).
        Wiki.js filtre STRICTEMENT par locale si le paramètre est fourni : si le
        wiki est mono-langue en "en" et qu'on force "fr", la recherche renvoie
        0 résultat même si le texte matche. Ne filtrer par locale que si
        explicitement demandé par l'appelant.
        """
        query = """
        query SearchPages($query: String!, $path: String, $locale: String) {
          pages {
            search(query: $query, path: $path, locale: $locale) {
              results { id title description path locale }
              suggestions
              totalHits
            }
          }
        }
        """
        variables = {"query": query_text, "path": path}
        if locale:
            variables["locale"] = locale
        data = await self._gql(query, variables)
        search = data.get("pages", {}).get("search", {})
        logger.info(f"Search '{query_text}': {search.get('totalHits', 0)} hits")
        return search

    async def get_page_tree(
        self,
        path: str = "",
        locale: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Récupère l'arborescence des pages (utile pour proposer un plan avant création)."""
        locale = locale or self.default_locale
        query = """
        query GetTree($path: String, $locale: String) {
          pages {
            tree(path: $path, locale: $locale, mode: ALL) {
              id path title depth isFolder parent pageId
            }
          }
        }
        """
        data = await self._gql(query, {"path": path, "locale": locale})
        tree = data.get("pages", {}).get("tree", [])
        logger.info(f"Retrieved tree: {len(tree)} nodes under '{path or '/'}'")
        return tree

    # ─────────────────────────────────────────────────────────────────────────
    # Écriture
    # ─────────────────────────────────────────────────────────────────────────

    async def create_page(
        self,
        path: str,
        title: str,
        content: str,
        description: str = "",
        editor: str = "markdown",
        tags: Optional[List[str]] = None,
        is_published: bool = True,
        is_private: bool = False,
        locale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Crée une nouvelle page. Échoue si le path existe déjà (PageDuplicateCreate)."""
        locale = locale or self.default_locale
        mutation = """
        mutation CreatePage(
          $content: String!, $description: String!, $editor: String!,
          $isPublished: Boolean!, $isPrivate: Boolean!, $locale: String!,
          $path: String!, $tags: [String]!, $title: String!
        ) {
          pages {
            create(
              content: $content, description: $description, editor: $editor,
              isPublished: $isPublished, isPrivate: $isPrivate, locale: $locale,
              path: $path, tags: $tags, title: $title
            ) {
              responseResult { succeeded errorCode slug message }
              page { id path title updatedAt }
            }
          }
        }
        """
        variables = {
            "content": content,
            "description": description,
            "editor": editor,
            "isPublished": is_published,
            "isPrivate": is_private,
            "locale": locale,
            "path": path.lstrip("/"),
            "tags": tags or [],
            "title": title,
        }
        data = await self._gql(mutation, variables)
        result = data.get("pages", {}).get("create", {})
        self._check_response_result(result, "create_page")

        logger.info(f"Created page: {path} (id={result.get('page', {}).get('id')})")
        return result["page"]

    async def update_page(
        self,
        page_id: int,
        content: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_published: Optional[bool] = None,
        editor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Met à jour une page EXISTANTE de façon sûre.

        Wiki.js ne fait pas de patch partiel réel côté API : on recharge donc
        la page actuelle et on complète les champs non fournis avant d'envoyer
        la mutation, pour ne jamais écraser le contenu par erreur.
        """
        current = await self.get_page(page_id=page_id)
        if not current:
            raise ValueError(f"Page id={page_id} not found, cannot update")

        mutation = """
        mutation UpdatePage(
          $id: Int!, $content: String!, $description: String!, $editor: String!,
          $isPublished: Boolean!, $tags: [String]!, $title: String!
        ) {
          pages {
            update(
              id: $id, content: $content, description: $description, editor: $editor,
              isPublished: $isPublished, tags: $tags, title: $title
            ) {
              responseResult { succeeded errorCode slug message }
              page { id path title updatedAt }
            }
          }
        }
        """
        variables = {
            "id": page_id,
            "content": content if content is not None else current["content"],
            "description": description if description is not None else current["description"],
            "editor": editor or current.get("editor", "markdown"),
            "isPublished": is_published if is_published is not None else current["isPublished"],
            "tags": tags if tags is not None else current.get("tags", []),
            "title": title if title is not None else current["title"],
        }
        data = await self._gql(mutation, variables)
        result = data.get("pages", {}).get("update", {})
        self._check_response_result(result, "update_page")

        logger.info(f"Updated page id={page_id} ({current.get('path')})")
        return result["page"]

    async def move_page(
        self,
        page_id: int,
        destination_path: str,
        destination_locale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Déplace/renomme une page (changement de path et/ou de locale)."""
        destination_locale = destination_locale or self.default_locale
        mutation = """
        mutation MovePage($id: Int!, $destinationPath: String!, $destinationLocale: String!) {
          pages {
            move(id: $id, destinationPath: $destinationPath, destinationLocale: $destinationLocale) {
              responseResult { succeeded errorCode slug message }
            }
          }
        }
        """
        data = await self._gql(mutation, {
            "id": page_id,
            "destinationPath": destination_path.lstrip("/"),
            "destinationLocale": destination_locale,
        })
        result = data.get("pages", {}).get("move", {})
        self._check_response_result(result, "move_page")

        logger.info(f"Moved page id={page_id} -> {destination_path}")
        return {"success": True, "id": page_id, "path": destination_path}

    async def delete_page(self, page_id: int) -> Dict[str, Any]:
        """Supprime définitivement une page."""
        mutation = """
        mutation DeletePage($id: Int!) {
          pages {
            delete(id: $id) {
              responseResult { succeeded errorCode slug message }
            }
          }
        }
        """
        data = await self._gql(mutation, {"id": page_id})
        result = data.get("pages", {}).get("delete", {})
        self._check_response_result(result, "delete_page")

        logger.info(f"Deleted page id={page_id}")
        return {"success": True, "id": page_id}

    # ─────────────────────────────────────────────────────────────────────────
    # Helper de haut niveau : upsert (create si absent, update sinon)
    # ─────────────────────────────────────────────────────────────────────────

    async def upsert_page(
        self,
        path: str,
        title: str,
        content: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        editor: str = "markdown",
        is_published: bool = True,
        locale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Crée la page si `path` n'existe pas, sinon la met à jour.
        Pratique pour la génération batch (N pages pour N besoins) : idempotent.
        """
        existing = await self.get_page(path=path, locale=locale)
        if existing:
            return await self.update_page(
                page_id=existing["id"],
                content=content,
                title=title,
                description=description,
                tags=tags,
                is_published=is_published,
                editor=editor,
            )
        return await self.create_page(
            path=path,
            title=title,
            content=content,
            description=description,
            tags=tags,
            editor=editor,
            is_published=is_published,
            locale=locale,
        )