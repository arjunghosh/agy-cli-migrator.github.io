import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
from pathlib import Path
import sys

# Add the parent directory to sys.path so we can import the module under test
sys.path.insert(0, str(Path(__file__).parent.parent))

from agy_migrator import (
    scan_claude_environment,
    scan_gemini_environment,
    diff_environments,
    create_backup,
    port_mcp_servers,
)

class TestAgyMigrator(unittest.TestCase):
    
    def setUp(self):
        self.mock_claude_dir = Path("/mock/home/.claude")
        self.mock_agents_dir = Path("/mock/home/.agents")
        self.mock_gemini_dir = Path("/mock/home/.gemini")

    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.iterdir")
    def test_scan_claude_environment(self, mock_iterdir, mock_exists, mock_is_dir):
        # Setup mocks for scan_claude_environment
        mock_exists.return_value = True
        mock_is_dir.return_value = True
        
        # Mockiterdir for skills folder
        mock_skill1 = MagicMock(spec=Path)
        mock_skill1.is_dir.return_value = True
        mock_skill1.name = "caveman"
        
        mock_skill2 = MagicMock(spec=Path)
        mock_skill2.is_dir.return_value = True
        mock_skill2.name = "ui-ux-pro-max"
        
        mock_iterdir.return_value = [mock_skill1, mock_skill2]

        # Mock mcp.json file opening
        mock_mcp_data = json.dumps({
            "mcpServers": {
                "github": {
                    "command": "npx",
                    "args": ["@modelcontextprotocol/server-github"]
                }
            }
        })
        
        with patch("builtins.open", mock_open(read_data=mock_mcp_data)):
            skills, mcps = scan_claude_environment(self.mock_claude_dir, self.mock_agents_dir)
            
        self.assertEqual(len(skills), 2)
        self.assertIn("caveman", skills)
        self.assertIn("ui-ux-pro-max", skills)
        self.assertEqual(len(mcps), 1)
        self.assertIn("github", mcps)

    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.iterdir")
    def test_scan_gemini_environment(self, mock_iterdir, mock_exists, mock_is_dir):
        # Setup mocks for scan_gemini_environment
        mock_exists.return_value = True
        mock_is_dir.return_value = True
        
        mock_skill = MagicMock(spec=Path)
        mock_skill.is_dir.return_value = True
        mock_skill.name = "bootstrap"
        mock_iterdir.return_value = [mock_skill]

        mock_settings_data = json.dumps({
            "mcpServers": {
                "serena": {
                    "command": "uvx",
                    "args": ["serena"]
                }
            }
        })
        
        with patch("builtins.open", mock_open(read_data=mock_settings_data)):
            skills, mcps = scan_gemini_environment(self.mock_gemini_dir)
            
        self.assertEqual(len(skills), 1)
        self.assertIn("bootstrap", skills)
        self.assertEqual(len(mcps), 1)
        self.assertIn("serena", mcps)

    def test_diff_environments(self):
        claude_skills = {"caveman", "ui-ux-pro-max", "bootstrap"}
        claude_mcps = {
            "github": {"command": "npx"},
            "serena": {"command": "uvx"}
        }
        gemini_skills = {"bootstrap"}
        gemini_mcps = {"serena": {"command": "uvx"}}
        
        skills_to_port, mcps_to_port = diff_environments(
            claude_skills, claude_mcps, gemini_skills, gemini_mcps
        )
        
        self.assertEqual(skills_to_port, {"caveman", "ui-ux-pro-max"})
        self.assertEqual(len(mcps_to_port), 1)
        self.assertIn("github", mcps_to_port)

    @patch("shutil.copy2")
    @patch("pathlib.Path.exists")
    def test_create_backup(self, mock_exists, mock_copy):
        mock_exists.return_value = True
        mock_file = Path("/mock/home/.gemini/settings.json")
        
        backup_path = create_backup(mock_file)
        
        self.assertTrue(backup_path.name.startswith("settings.json."))
        self.assertTrue(backup_path.name.endswith(".bak"))
        mock_copy.assert_called_once()

    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    @patch("json.dump")
    @patch("pathlib.Path.exists")
    def test_port_mcp_servers(self, mock_exists, mock_dump, mock_load, mock_file_open):
        mock_exists.return_value = True
        mock_load.return_value = {
            "mcpServers": {
                "serena": {"command": "uvx"}
            }
        }
        
        mcps_to_port = {
            "github": {"command": "npx"}
        }
        
        port_mcp_servers(Path("/mock/home/.gemini/settings.json"), mcps_to_port, backup=False)
        
        # Verify the merge result passed to json.dump
        called_args = mock_dump.call_args[0][0]
        self.assertIn("github", called_args["mcpServers"])
        self.assertIn("serena", called_args["mcpServers"])

if __name__ == "__main__":
    unittest.main()
