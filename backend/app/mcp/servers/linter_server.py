"""
MCP Server pour lint/format multi-language.

Supporte: Python (black, ruff), JavaScript/TypeScript (prettier, eslint), 
Go (gofmt), Rust (rustfmt), etc.
"""
import subprocess
import os
from pathlib import Path
from typing import Dict, Any, List, Optional


class LinterMCP:
    """MCP Server pour lint et format de code."""
    
    LANGUAGE_TOOLS = {
        "python": {
            "formatter": "black",
            "linter": "ruff",
            "extensions": [".py"]
        },
        "javascript": {
            "formatter": "prettier",
            "linter": "eslint",
            "extensions": [".js", ".jsx"]
        },
        "typescript": {
            "formatter": "prettier",
            "linter": "eslint",
            "extensions": [".ts", ".tsx"]
        },
        "go": {
            "formatter": "gofmt",
            "linter": "golint",
            "extensions": [".go"]
        },
        "rust": {
            "formatter": "rustfmt",
            "linter": "clippy",
            "extensions": [".rs"]
        },
        "json": {
            "formatter": "prettier",
            "extensions": [".json"]
        },
        "yaml": {
            "formatter": "prettier",
            "extensions": [".yml", ".yaml"]
        }
    }
    
    def __init__(self):
        self.name = "linter"
        self.version = "1.0.0"
    
    async def format_file(
        self,
        path: str,
        auto_fix: bool = True,
        check_only: bool = False
    ) -> Dict[str, Any]:
        """
        Format un fichier.
        
        Args:
            path: Chemin du fichier
            auto_fix: Appliquer les corrections automatiquement
            check_only: Vérifier seulement (pas de modifications)
        
        Returns:
            {
                "success": bool,
                "formatted": bool,
                "issues": List[str],
                "output": str
            }
        """
        # Detect language
        language = self._detect_language(path)
        
        if not language:
            return {
                "success": False,
                "error": f"Unsupported file type: {Path(path).suffix}",
                "formatted": False
            }
        
        tools = self.LANGUAGE_TOOLS[language]
        
        results = {
            "success": True,
            "formatted": False,
            "issues": [],
            "output": "",
            "language": language
        }
        
        # 1. Format
        if "formatter" in tools and not check_only:
            format_result = await self._format(path, language, tools["formatter"])
            results["formatted"] = format_result["success"]
            results["output"] += format_result.get("output", "")
        
        # 2. Lint (si auto_fix activé)
        if "linter" in tools and auto_fix:
            lint_result = await self._lint(path, language, tools["linter"], auto_fix)
            results["issues"].extend(lint_result.get("issues", []))
            results["output"] += "\n" + lint_result.get("output", "")
            results["success"] = results["success"] and lint_result["success"]
        
        return results
    
    async def format_directory(
        self,
        path: str,
        recursive: bool = True,
        extensions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Format tous les fichiers d'un répertoire.
        
        Args:
            path: Chemin du répertoire
            recursive: Parcourir récursivement
            extensions: Extensions à formater (optionnel)
        
        Returns:
            {
                "success": bool,
                "files_processed": int,
                "files_formatted": int,
                "errors": List[str]
            }
        """
        path_obj = Path(path)
        
        if not path_obj.is_dir():
            return {
                "success": False,
                "error": "Path is not a directory"
            }
        
        # Collect files
        files = []
        if recursive:
            for ext in extensions or ["**/*"]:
                files.extend(path_obj.glob(ext if ext.startswith("**") else f"**/*{ext}"))
        else:
            for ext in extensions or ["*"]:
                files.extend(path_obj.glob(ext if ext.startswith("*") else f"*{ext}"))
        
        files = [f for f in files if f.is_file()]
        
        results = {
            "success": True,
            "files_processed": 0,
            "files_formatted": 0,
            "errors": []
        }
        
        for file in files:
            try:
                result = await self.format_file(str(file), auto_fix=True)
                results["files_processed"] += 1
                if result.get("formatted"):
                    results["files_formatted"] += 1
            except Exception as e:
                results["errors"].append(f"{file}: {str(e)}")
                results["success"] = False
        
        return results
    
    def _detect_language(self, path: str) -> Optional[str]:
        """Détecte le langage depuis l'extension."""
        ext = Path(path).suffix.lower()
        
        for lang, config in self.LANGUAGE_TOOLS.items():
            if ext in config["extensions"]:
                return lang
        
        return None
    
    async def _format(
        self,
        path: str,
        language: str,
        formatter: str
    ) -> Dict[str, Any]:
        """Applique le formatter."""
        
        if formatter == "black":
            return await self._run_black(path)
        elif formatter == "prettier":
            return await self._run_prettier(path)
        elif formatter == "gofmt":
            return await self._run_gofmt(path)
        elif formatter == "rustfmt":
            return await self._run_rustfmt(path)
        else:
            return {
                "success": False,
                "error": f"Unknown formatter: {formatter}"
            }
    
    async def _lint(
        self,
        path: str,
        language: str,
        linter: str,
        auto_fix: bool
    ) -> Dict[str, Any]:
        """Applique le linter."""
        
        if linter == "ruff":
            return await self._run_ruff(path, auto_fix)
        elif linter == "eslint":
            return await self._run_eslint(path, auto_fix)
        elif linter == "golint":
            return await self._run_golint(path)
        elif linter == "clippy":
            return await self._run_clippy(path, auto_fix)
        else:
            return {
                "success": False,
                "error": f"Unknown linter: {linter}"
            }
    
    # === Python Tools ===
    
    async def _run_black(self, path: str) -> Dict[str, Any]:
        """Exécute Black (Python formatter)."""
        try:
            result = subprocess.run(
                ["black", path],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout + result.stderr
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "black not installed (pip install black)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _run_ruff(self, path: str, auto_fix: bool) -> Dict[str, Any]:
        """Exécute Ruff (Python linter)."""
        cmd = ["ruff", "check", path]
        
        if auto_fix:
            cmd.append("--fix")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Parse issues
            issues = []
            for line in result.stdout.split("\n"):
                if line.strip():
                    issues.append(line)
            
            return {
                "success": result.returncode == 0,
                "issues": issues,
                "output": result.stdout + result.stderr
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "ruff not installed (pip install ruff)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # === JavaScript/TypeScript Tools ===
    
    async def _run_prettier(self, path: str) -> Dict[str, Any]:
        """Exécute Prettier."""
        try:
            result = subprocess.run(
                ["npx", "prettier", "--write", path],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout + result.stderr
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "prettier not available (npm install -D prettier)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _run_eslint(self, path: str, auto_fix: bool) -> Dict[str, Any]:
        """Exécute ESLint."""
        cmd = ["npx", "eslint", path]
        
        if auto_fix:
            cmd.append("--fix")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Parse issues
            issues = []
            for line in result.stdout.split("\n"):
                if "error" in line.lower() or "warning" in line.lower():
                    issues.append(line)
            
            return {
                "success": result.returncode == 0,
                "issues": issues,
                "output": result.stdout + result.stderr
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "eslint not available (npm install -D eslint)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # === Go Tools ===
    
    async def _run_gofmt(self, path: str) -> Dict[str, Any]:
        """Exécute gofmt."""
        try:
            result = subprocess.run(
                ["gofmt", "-w", path],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout + result.stderr
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "gofmt not available (install Go)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _run_golint(self, path: str) -> Dict[str, Any]:
        """Exécute golint."""
        try:
            result = subprocess.run(
                ["golint", path],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            issues = [line for line in result.stdout.split("\n") if line.strip()]
            
            return {
                "success": result.returncode == 0,
                "issues": issues,
                "output": result.stdout + result.stderr
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "golint not available (go install ...)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # === Rust Tools ===
    
    async def _run_rustfmt(self, path: str) -> Dict[str, Any]:
        """Exécute rustfmt."""
        try:
            result = subprocess.run(
                ["rustfmt", path],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout + result.stderr
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "rustfmt not available (rustup component add rustfmt)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _run_clippy(self, path: str, auto_fix: bool) -> Dict[str, Any]:
        """Exécute clippy (Rust linter)."""
        cmd = ["cargo", "clippy"]
        
        if auto_fix:
            cmd.append("--fix")
        
        # clippy doit être lancé depuis la racine du projet
        project_root = self._find_cargo_root(path)
        
        try:
            result = subprocess.run(
                cmd,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            issues = []
            for line in result.stdout.split("\n"):
                if "warning:" in line or "error:" in line:
                    issues.append(line)
            
            return {
                "success": result.returncode == 0,
                "issues": issues,
                "output": result.stdout + result.stderr
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "clippy not available (rustup component add clippy)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _find_cargo_root(self, path: str) -> str:
        """Trouve la racine du projet Cargo (Cargo.toml)."""
        current = Path(path).parent
        
        while current != current.parent:
            if (current / "Cargo.toml").exists():
                return str(current)
            current = current.parent
        
        return str(Path(path).parent)


# MCP Server interface
async def handle_mcp_call(method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP calls."""
    server = LinterMCP()
    
    if method == "format_file":
        return await server.format_file(**params)
    elif method == "format_directory":
        return await server.format_directory(**params)
    else:
        raise ValueError(f"Unknown method: {method}")