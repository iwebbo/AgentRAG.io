"""
MCP Server pour exécution de tests unitaires multi-framework.

Supporte: pytest, jest, junit, go test, cargo test, etc.
"""
import subprocess
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


class TestRunnerMCP:
    """MCP Server pour tests unitaires."""
    
    FRAMEWORK_DETECTION = {
        "pytest": ["pytest.ini", "setup.py", "pyproject.toml"],
        "jest": ["jest.config.js", "jest.config.ts", "package.json"],
        "junit": ["pom.xml", "build.gradle"],
        "go": ["go.mod"],
        "cargo": ["Cargo.toml"],
        "rspec": ["Gemfile", ".rspec"]
    }
    
    def __init__(self):
        self.name = "test_runner"
        self.version = "1.0.0"
    
    async def run_tests(
        self,
        path: str,
        framework: str = "auto",
        verbose: bool = True,
        coverage: bool = False
    ) -> Dict[str, Any]:
        """
        Lance les tests unitaires.
        
        Args:
            path: Chemin du projet
            framework: Framework à utiliser (auto|pytest|jest|junit|go|cargo)
            verbose: Mode verbose
            coverage: Activer la couverture de code
        
        Returns:
            {
                "passed": bool,
                "summary": str,
                "total": int,
                "passed_count": int,
                "failed_count": int,
                "skipped_count": int,
                "duration": float,
                "coverage": float|None,
                "output": str
            }
        """
        # Auto-detect framework si nécessaire
        if framework == "auto":
            framework = self._detect_framework(path)
        
        if not framework:
            return {
                "passed": False,
                "error": "No test framework detected",
                "summary": "Unable to detect test framework"
            }
        
        # Exécuter tests selon framework
        if framework == "pytest":
            return await self._run_pytest(path, verbose, coverage)
        elif framework == "jest":
            return await self._run_jest(path, verbose, coverage)
        elif framework == "junit":
            return await self._run_junit(path, verbose)
        elif framework == "go":
            return await self._run_go_test(path, verbose, coverage)
        elif framework == "cargo":
            return await self._run_cargo_test(path, verbose)
        else:
            return {
                "passed": False,
                "error": f"Unsupported framework: {framework}",
                "summary": f"Framework {framework} not supported"
            }
    
    def _detect_framework(self, path: str) -> Optional[str]:
        """Auto-détecte le framework de tests."""
        path_obj = Path(path)
        
        for framework, markers in self.FRAMEWORK_DETECTION.items():
            for marker in markers:
                if (path_obj / marker).exists():
                    # Validation additionnelle
                    if framework == "pytest":
                        # Check si pytest est installé
                        if self._has_pytest_tests(path):
                            return "pytest"
                    elif framework == "jest":
                        # Check package.json pour jest
                        if self._has_jest_config(path):
                            return "jest"
                    else:
                        return framework
        
        return None
    
    def _has_pytest_tests(self, path: str) -> bool:
        """Vérifie si des tests pytest existent."""
        path_obj = Path(path)
        # Cherche fichiers test_*.py ou *_test.py
        for pattern in ["**/test_*.py", "**/*_test.py"]:
            if list(path_obj.glob(pattern)):
                return True
        return False
    
    def _has_jest_config(self, path: str) -> bool:
        """Vérifie configuration Jest."""
        package_json = Path(path) / "package.json"
        if package_json.exists():
            try:
                with open(package_json, 'r') as f:
                    data = json.load(f)
                    # Check devDependencies ou dependencies
                    deps = {**data.get("devDependencies", {}), **data.get("dependencies", {})}
                    return "jest" in deps
            except:
                pass
        return False
    
    async def _run_pytest(
        self,
        path: str,
        verbose: bool,
        coverage: bool
    ) -> Dict[str, Any]:
        """Exécute pytest."""
        cmd = ["pytest"]
        
        if verbose:
            cmd.append("-v")
        
        if coverage:
            cmd.extend(["--cov", "--cov-report=term"])
        
        # JSON output pour parsing
        cmd.append("--tb=short")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=path,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            output = result.stdout + result.stderr
            
            # Parse output basique
            passed = result.returncode == 0
            
            # Extract stats (pattern: "X passed, Y failed")
            stats = self._parse_pytest_output(output)
            
            return {
                "passed": passed,
                "summary": f"pytest: {stats['summary']}",
                "total": stats["total"],
                "passed_count": stats["passed"],
                "failed_count": stats["failed"],
                "skipped_count": stats.get("skipped", 0),
                "duration": stats.get("duration", 0.0),
                "coverage": stats.get("coverage"),
                "output": output,
                "framework": "pytest"
            }
            
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "error": "Tests timed out (5min limit)",
                "summary": "Timeout"
            }
        except Exception as e:
            return {
                "passed": False,
                "error": str(e),
                "summary": f"Failed to run pytest: {str(e)}"
            }
    
    def _parse_pytest_output(self, output: str) -> Dict[str, Any]:
        """Parse la sortie pytest."""
        stats = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0,
            "duration": 0.0,
            "coverage": None,
            "summary": "No tests run"
        }
        
        # Pattern: "5 passed, 2 failed, 1 skipped in 1.23s"
        import re
        
        passed_match = re.search(r'(\d+)\s+passed', output)
        if passed_match:
            stats["passed"] = int(passed_match.group(1))
        
        failed_match = re.search(r'(\d+)\s+failed', output)
        if failed_match:
            stats["failed"] = int(failed_match.group(1))
        
        skipped_match = re.search(r'(\d+)\s+skipped', output)
        if skipped_match:
            stats["skipped"] = int(skipped_match.group(1))
        
        stats["total"] = stats["passed"] + stats["failed"] + stats["skipped"]
        
        # Duration
        duration_match = re.search(r'in\s+([\d.]+)s', output)
        if duration_match:
            stats["duration"] = float(duration_match.group(1))
        
        # Coverage
        coverage_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', output)
        if coverage_match:
            stats["coverage"] = int(coverage_match.group(1))
        
        # Summary
        if stats["total"] > 0:
            if stats["failed"] == 0:
                stats["summary"] = f"✅ {stats['passed']} passed"
            else:
                stats["summary"] = f"❌ {stats['failed']} failed, {stats['passed']} passed"
        
        return stats
    
    async def _run_jest(
        self,
        path: str,
        verbose: bool,
        coverage: bool
    ) -> Dict[str, Any]:
        """Exécute Jest."""
        cmd = ["npm", "test", "--"]
        
        if coverage:
            cmd.append("--coverage")
        
        # JSON reporter
        cmd.append("--json")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=path,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Jest retourne JSON
            try:
                data = json.loads(result.stdout)
                
                passed = data.get("success", False)
                num_passed = data.get("numPassedTests", 0)
                num_failed = data.get("numFailedTests", 0)
                num_total = data.get("numTotalTests", 0)
                
                return {
                    "passed": passed,
                    "summary": f"Jest: {num_passed}/{num_total} passed",
                    "total": num_total,
                    "passed_count": num_passed,
                    "failed_count": num_failed,
                    "skipped_count": 0,
                    "duration": 0.0,
                    "coverage": None,
                    "output": result.stdout,
                    "framework": "jest"
                }
            except json.JSONDecodeError:
                # Fallback: parse text output
                output = result.stdout + result.stderr
                passed = "Tests passed" in output or result.returncode == 0
                
                return {
                    "passed": passed,
                    "summary": "Jest tests completed",
                    "output": output,
                    "framework": "jest"
                }
            
        except Exception as e:
            return {
                "passed": False,
                "error": str(e),
                "summary": f"Failed to run Jest: {str(e)}"
            }
    
    async def _run_junit(self, path: str, verbose: bool) -> Dict[str, Any]:
        """Exécute JUnit (Maven ou Gradle)."""
        # Detect Maven ou Gradle
        if (Path(path) / "pom.xml").exists():
            cmd = ["mvn", "test"]
        elif (Path(path) / "build.gradle").exists():
            cmd = ["gradle", "test"]
        else:
            return {
                "passed": False,
                "error": "No Maven or Gradle config found"
            }
        
        try:
            result = subprocess.run(
                cmd,
                cwd=path,
                capture_output=True,
                text=True,
                timeout=600  # Java tests peuvent être lents
            )
            
            output = result.stdout + result.stderr
            passed = result.returncode == 0
            
            return {
                "passed": passed,
                "summary": "JUnit tests completed",
                "output": output,
                "framework": "junit"
            }
            
        except Exception as e:
            return {
                "passed": False,
                "error": str(e),
                "summary": f"Failed to run JUnit: {str(e)}"
            }
    
    async def _run_go_test(
        self,
        path: str,
        verbose: bool,
        coverage: bool
    ) -> Dict[str, Any]:
        """Exécute go test."""
        cmd = ["go", "test", "./..."]
        
        if verbose:
            cmd.append("-v")
        
        if coverage:
            cmd.extend(["-cover", "-coverprofile=coverage.out"])
        
        try:
            result = subprocess.run(
                cmd,
                cwd=path,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            output = result.stdout + result.stderr
            passed = result.returncode == 0
            
            # Parse coverage
            coverage_pct = None
            if coverage:
                import re
                match = re.search(r'coverage:\s+([\d.]+)%', output)
                if match:
                    coverage_pct = float(match.group(1))
            
            return {
                "passed": passed,
                "summary": f"Go tests {'passed' if passed else 'failed'}",
                "coverage": coverage_pct,
                "output": output,
                "framework": "go"
            }
            
        except Exception as e:
            return {
                "passed": False,
                "error": str(e),
                "summary": f"Failed to run go test: {str(e)}"
            }
    
    async def _run_cargo_test(self, path: str, verbose: bool) -> Dict[str, Any]:
        """Exécute cargo test (Rust)."""
        cmd = ["cargo", "test"]
        
        if verbose:
            cmd.append("--verbose")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=path,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            output = result.stdout + result.stderr
            passed = result.returncode == 0
            
            return {
                "passed": passed,
                "summary": f"Rust tests {'passed' if passed else 'failed'}",
                "output": output,
                "framework": "cargo"
            }
            
        except Exception as e:
            return {
                "passed": False,
                "error": str(e),
                "summary": f"Failed to run cargo test: {str(e)}"
            }


# MCP Server interface
async def handle_mcp_call(method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP calls."""
    server = TestRunnerMCP()
    
    if method == "run_tests":
        return await server.run_tests(**params)
    else:
        raise ValueError(f"Unknown method: {method}")