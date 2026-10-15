"""Configuration management for Screeni-py."""

import configparser
import glob
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class ConfigManager:
    """Manages the application configuration and presets."""

    def __init__(self, preset_dir: str = 'config/presets'):
        """Initializes ConfigManager with default configuration and preset directory."""
        self.preset_dir = Path(preset_dir)
        self.preset_dir.mkdir(parents=True, exist_ok=True)
        self.config = self._load_default_config()
        
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default configuration values."""
        return {
            'period': '1y',
            'duration': '1d',
            'backtest_period': 30,
            'min_price': 10,
            'max_price': 10000,
            'volume_ratio': 2.5,
            'consolidation_percentage': 10,
            'shuffle_enabled': True,
            'cache_enabled': True,
            'stage2_enabled': False,
            'use_ema': False,
        }
    
    def _get_color_text(self):
        """Lazy import colorText to avoid circular imports."""
        from screeni.ui.color import colorText
        return colorText
    
    def save_preset(self, name: str, config: Dict[str, Any]) -> None:
        """Save a named preset configuration."""
        preset_file = self.preset_dir / f"{name}.json"
        with open(preset_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Use lazy import for color
        color = self._get_color_text()
        print(f"{color.GREEN}✅ Preset '{name}' saved{color.RESET}")
    
    def load_preset(self, name: str) -> Dict[str, Any]:
        """Load a named preset configuration."""
        preset_file = self.preset_dir / f"{name}.json"
        if not preset_file.exists():
            color = self._get_color_text()
            print(f"{color.RED}❌ Preset '{name}' not found{color.RESET}")
            return self.config
        
        with open(preset_file, 'r') as f:
            return json.load(f)
    
    def list_presets(self) -> List[str]:
        """List all available preset names."""
        return [f.stem for f in self.preset_dir.glob("*.json")]
    
    def delete_preset(self, name: str) -> None:
        """Delete a named preset file."""
        preset_file = self.preset_dir / f"{name}.json"
        if preset_file.exists():
            preset_file.unlink()
            color = self._get_color_text()
            print(f"{color.YELLOW}🗑️  Preset '{name}' deleted{color.RESET}")
    
    def deleteStockData(self, exclude_file: Optional[str] = None) -> None:
        """Delete cached pkl files in the current directory."""
        for f in glob.glob("*.pkl"):
            if exclude_file and exclude_file in f:
                continue
            try:
                os.remove(f)
                color = self._get_color_text()
                print(f"{color.YELLOW}🗑️  Removed: {f}{color.RESET}")
            except OSError:
                pass
    
    def setConfig(self, parser_obj: configparser.ConfigParser, 
                  default: bool = False, showFileCreatedText: bool = True) -> None:
        """Saves current configuration to screenipy.ini."""
        # Implementation here
        pass
    
    def getConfig(self, parser_obj: configparser.ConfigParser) -> None:
        """Loads configuration from screenipy.ini."""
        # Implementation here
        pass
    
    def showConfigFile(self) -> None:
        """Prints the current screenipy.ini file content."""
        # Implementation here
        pass
    
    def checkConfigFile(self) -> bool:
        """Checks if screenipy.ini exists in the current directory."""
        return Path("screenipy.ini").exists()
    
    def getPeriodNumeric(self) -> int:
        """Extracts the numeric part of the period string."""
        period_str = self.config.get('period', '1y')
        match = re.match(r'(\d+)', period_str)
        return int(match.group(1)) if match else 1
