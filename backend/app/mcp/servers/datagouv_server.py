import httpx
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://www.data.gouv.fr/api/1"
BASE_URL_V2 = "https://www.data.gouv.fr/api/2"  # topics only available in v2
TIMEOUT = 15.0

# Valid sort values per endpoint (data.gouv.fr API v1)
_DATASET_SORT_VALUES = {"title", "created", "last_update", "reuses", "followers", "views",
                        "-title", "-created", "-last_update", "-reuses", "-followers", "-views"}
_ORG_SORT_VALUES = {"name", "reuses", "datasets", "followers", "views", "created", "last_modified",
                    "-name", "-reuses", "-datasets", "-followers", "-views", "-created", "-last_modified"}


class DataGouvMCPServer:
    """
    MCP Server pour data.gouv.fr.

    Wraps the public REST API of the French national Open Data platform.
    No API key required for read-only operations.

    Available methods:
        - search_datasets       : full-text search across the catalogue
        - get_dataset           : fetch a single dataset by slug or id
        - list_dataset_resources: list downloadable resources of a dataset
        - get_resource          : fetch metadata for a single resource
        - search_organizations  : search producers/organisations
        - get_organization      : fetch a single organisation
        - list_topics           : list available thematic topics
        - get_topic             : fetch datasets grouped under a topic

    Valid sort values:
        datasets     : title | created | last_update | reuses | followers | views (prefix - to reverse)
        organizations: name | reuses | datasets | followers | views | created | last_modified (prefix - to reverse)
        Omit sort param for relevance ordering (API default).
    """

    def __init__(self, page_size: int = 20):
        self.page_size = min(page_size, 100)
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "datagouv-mcp-server/1.0",
        }
        logger.info("DataGouvMCPServer initialized (endpoint: %s)", BASE_URL)

    # ------------------------------------------------------------------ #
    # Datasets
    # ------------------------------------------------------------------ #

    async def search_datasets(
        self,
        q: str,
        page: int = 1,
        page_size: Optional[int] = None,
        organization: Optional[str] = None,
        tag: Optional[str] = None,
        license: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full-text search across the data.gouv.fr dataset catalogue.

        Args:
            q           : Search query string.
            page        : Page number (1-indexed).
            page_size   : Results per page (defaults to server page_size).
            organization: Filter by organisation slug or id.
            tag         : Filter by tag.
            license     : Filter by SPDX license identifier (e.g. "fr-lo").
            sort        : Sort field. Valid values:
                          title | created | last_update | reuses | followers | views
                          Prefix with - for descending (e.g. "-created").
                          Omit for relevance ordering (API default).

        Returns:
            {
                "data": [...],
                "total": int,
                "page": int,
                "page_size": int,
                "next_page": str|null,
                "previous_page": str|null,
            }
        """
        params: Dict[str, Any] = {
            "q": q,
            "page": page,
            "page_size": page_size or self.page_size,
        }
        # Only inject sort if it's a known valid value — API returns 400 on unknown values
        if sort and sort in _DATASET_SORT_VALUES:
            params["sort"] = sort
        elif sort:
            logger.warning(
                "search_datasets: invalid sort=%r ignored. Valid: %s",
                sort, sorted(_DATASET_SORT_VALUES)
            )

        if organization:
            params["organization"] = organization
        if tag:
            params["tag"] = tag
        if license:
            params["license"] = license

        async with httpx.AsyncClient(headers=self.headers, timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL}/datasets/", params=params)
            response.raise_for_status()
            data = response.json()

        logger.info(
            "search_datasets q=%r → %d results (page %d)",
            q, data.get("total", 0), page,
        )
        return data

    async def get_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """
        Fetch a single dataset by its slug or UUID.

        Args:
            dataset_id: Dataset slug (e.g. "population-legale-2021") or UUID.

        Returns:
            Full dataset object with metadata, resources, organisation, etc.
        """
        async with httpx.AsyncClient(headers=self.headers, timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL}/datasets/{dataset_id}/")
            response.raise_for_status()
            data = response.json()

        logger.info("get_dataset id=%r → %s", dataset_id, data.get("title", "?"))
        return data

    async def list_dataset_resources(
        self,
        dataset_id: str,
        page: int = 1,
        page_size: Optional[int] = None,
        type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List downloadable resources attached to a dataset.

        Args:
            dataset_id : Dataset slug or UUID.
            page       : Page number.
            page_size  : Results per page.
            type       : Filter by resource type ("main", "documentation",
                         "update", "api", "code", "other").

        Returns:
            Paginated list of resource objects.
        """
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size or self.page_size,
        }
        if type:
            params["type"] = type

        async with httpx.AsyncClient(headers=self.headers, timeout=TIMEOUT) as client:
            response = await client.get(
                f"{BASE_URL}/datasets/{dataset_id}/resources/", params=params
            )
            response.raise_for_status()
            data = response.json()

        logger.info(
            "list_dataset_resources dataset=%r → %d resources",
            dataset_id, data.get("total", 0),
        )
        return data

    async def get_resource(self, dataset_id: str, resource_id: str) -> Dict[str, Any]:
        """
        Fetch metadata for a single resource.

        Args:
            dataset_id : Parent dataset slug or UUID.
            resource_id: Resource UUID.

        Returns:
            Resource object (url, format, filesize, checksum, etc.).
        """
        async with httpx.AsyncClient(headers=self.headers, timeout=TIMEOUT) as client:
            response = await client.get(
                f"{BASE_URL}/datasets/{dataset_id}/resources/{resource_id}/"
            )
            response.raise_for_status()
            data = response.json()

        logger.info(
            "get_resource dataset=%r resource=%r → %s",
            dataset_id, resource_id, data.get("title", "?"),
        )
        return data

    # ------------------------------------------------------------------ #
    # Organisations
    # ------------------------------------------------------------------ #

    async def search_organizations(
        self,
        q: str,
        page: int = 1,
        page_size: Optional[int] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search organisations (data producers) on data.gouv.fr.

        Args:
            q        : Search query string.
            page     : Page number.
            page_size: Results per page.
            sort     : Sort field. Valid values:
                       name | reuses | datasets | followers | views | created | last_modified
                       Prefix with - for descending. Omit for relevance ordering.

        Returns:
            Paginated list of organisation objects.
        """
        params: Dict[str, Any] = {
            "q": q,
            "page": page,
            "page_size": page_size or self.page_size,
        }
        if sort and sort in _ORG_SORT_VALUES:
            params["sort"] = sort
        elif sort:
            logger.warning(
                "search_organizations: invalid sort=%r ignored. Valid: %s",
                sort, sorted(_ORG_SORT_VALUES)
            )

        async with httpx.AsyncClient(headers=self.headers, timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL}/organizations/", params=params)
            response.raise_for_status()
            data = response.json()

        logger.info("search_organizations q=%r → %d results", q, data.get("total", 0))
        return data

    async def get_organization(self, org_id: str) -> Dict[str, Any]:
        """
        Fetch a single organisation by slug or UUID.

        Args:
            org_id: Organisation slug (e.g. "ministere-de-linterieur") or UUID.

        Returns:
            Organisation object with description, logo, metrics, etc.
        """
        async with httpx.AsyncClient(headers=self.headers, timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL}/organizations/{org_id}/")
            response.raise_for_status()
            data = response.json()

        logger.info("get_organization id=%r → %s", org_id, data.get("name", "?"))
        return data

    # ------------------------------------------------------------------ #
    # Topics (thematic groupings)
    # ------------------------------------------------------------------ #

    async def list_topics(
        self, page: int = 1, page_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        List all thematic topics available on data.gouv.fr.

        Returns:
            Paginated list of topic objects (id, name, slug, description).
        """
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size or self.page_size,
        }
        async with httpx.AsyncClient(headers=self.headers, timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL_V2}/topics/", params=params)
            response.raise_for_status()
            data = response.json()

        logger.info("list_topics → %d topics", data.get("total", 0))
        return data

    async def get_topic(self, topic_id: str) -> Dict[str, Any]:
        """
        Fetch datasets grouped under a thematic topic.

        Args:
            topic_id: Topic slug or UUID.

        Returns:
            Topic object including its featured datasets list.
        """
        async with httpx.AsyncClient(headers=self.headers, timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL_V2}/topics/{topic_id}/")
            response.raise_for_status()
            data = response.json()

        logger.info("get_topic id=%r → %s", topic_id, data.get("name", "?"))
        return data