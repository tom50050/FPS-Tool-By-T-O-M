# -*- coding: utf-8 -*-
"""
T O M - PUBG FPS Settings
Desktop application for adjusting PUBG Mobile FPS settings
using PyWebView

Main application file
"""

import os
import sys
import shutil
import subprocess
import threading
import time
import json
import base64
import webview
from pathlib import Path


class PUBGFPSApi:
    """
    API class for communicating with HTML UI via PyWebView
    Provides functions callable from JavaScript
    """

    def __init__(self):
        """Initialize API"""
        self.base_path = self._get_base_path()
        self.data_path = self.base_path / 'Data'
        self.adb_path = self.data_path / 'adb.exe'
        self.profiles_file = self.base_path / 'profiles.json'
        self._device_id = None
        self._current_preset = None
        self._current_source = None

        print("BASE PATH =", self.base_path)
        print("DATA PATH =", self.data_path)
        print("ADB PATH =", self.adb_path)
        print("ADB EXISTS =", self.adb_path.exists())

        # Settings file paths
        self.preset_paths = {
            'HD': self.data_path / 'HD' / 'Active.sav',
            'HDR': self.data_path / 'HDR' / 'Active.sav',
            'Ultra HDR': self.data_path / 'UltraHDR' / 'Active.sav',
        }

    def _get_base_path(self) -> Path:
        """Get the base application path"""
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent
        return Path(__file__).parent

    def _run_adb(self, args: list, timeout: int = 30) -> tuple:
        """Run ADB command and return (returncode, stdout, stderr)"""
        try:
            result = subprocess.run(
                [str(self.adb_path)] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return -1, '', str(e)

    def _find_gameloop_device(self) -> str:
        """Find Gameloop device using ADB"""
        try:
            code, stdout, stderr = self._run_adb(['devices'], timeout=15)
            if code != 0:
                return None
            lines = stdout.strip().split('\n')
            for line in lines[1:]:
                if '\t' in line:
                    parts = line.split('\t')
                    if len(parts) >= 2 and parts[1].strip() == 'device':
                        return parts[0].strip()
            return None
        except Exception as e:
            print(f"Error finding device: {e}")
            return None

    def _is_device_connected(self) -> bool:
        """Check if a device is connected"""
        if not self._device_id:
            self._device_id = self._find_gameloop_device()
        return self._device_id is not None

    def _stop_pubg(self) -> bool:
        """Stop PUBG on device"""
        if not self._is_device_connected():
            return False
        code, _, _ = self._run_adb(
            ['-s', self._device_id, 'shell', 'am', 'force-stop', 'com.tencent.ig'],
            timeout=20
        )
        return code == 0

    def _start_pubg(self) -> bool:
        """Start PUBG on device"""
        if not self._is_device_connected():
            return False
        code, _, _ = self._run_adb(
            ['-s', self._device_id, 'shell', 'monkey', '-p', 'com.tencent.ig',
             '-c', 'android.intent.category.LAUNCHER', '1'],
            timeout=20
        )
        return code == 0

    def _push_settings_file(self, source_file: Path) -> bool:
        """Push settings file to device"""
        if not self._is_device_connected():
            return False
        remote_path = '/sdcard/Android/data/com.tencent.ig/files/UE4Game/ShadowTrackerExtra/ShadowTrackerExtra/Saved/SaveGames/Active.sav'
        code, stdout, stderr = self._run_adb(
            ['-s', self._device_id, 'push', str(source_file), remote_path],
            timeout=60
        )
        return code == 0

    def _verify_file(self) -> bool:
        """Verify file exists on device"""
        if not self._is_device_connected():
            return False
        remote_path = '/sdcard/Android/data/com.tencent.ig/files/UE4Game/ShadowTrackerExtra/ShadowTrackerExtra/Saved/SaveGames/Active.sav'
        code, stdout, stderr = self._run_adb(
            ['-s', self._device_id, 'shell', 'ls', remote_path],
            timeout=20
        )
        return code == 0 and 'No such file' not in stderr and 'No such file' not in stdout

    def _check_file_exists(self, preset_name: str) -> bool:
        """Check if preset file exists"""
        path = self.preset_paths.get(preset_name)
        if not path:
            return False
        return path.exists()

    # ═══════════════════════════════════════════════════════════════
    # PUBLIC API - callable from JavaScript
    # ═══════════════════════════════════════════════════════════════

    def check_status(self) -> dict:
        """
        Check overall system status
        Returns: {"adb_available": bool, "device_connected": bool, "message": str}
        """
        adb_available = self.adb_path.exists()
        if not adb_available:
            return {"adb_available": False, "device_connected": False, "message": "ADB not found"}
        device_connected = self._is_device_connected()
        if not device_connected:
            return {"adb_available": True, "device_connected": False, "message": "Device not connected"}
        return {"adb_available": True, "device_connected": True, "message": f"Device: {self._device_id}"}

    def execute_preset(self, preset_name: str) -> dict:
        """
        Execute full preset application
        preset_name: "HD", "HDR", "Ultra HDR"
        Returns: {"success": bool, "message": str}
        """
        # 1. Check ADB
        if not self.adb_path.exists():
            return {"success": False, "message": "ADB not found"}

        # 2. Find device
        self._device_id = self._find_gameloop_device()
        if not self._device_id:
            return {"success": False, "message": "Device not connected"}

        # 3. Check preset file
        source = self.preset_paths.get(preset_name)
        if not source or not source.exists():
            return {"success": False, "message": f"Preset file not found: {preset_name}"}

        # 4. Stop PUBG
        if not self._stop_pubg():
            return {"success": False, "message": "Failed to stop PUBG"}

        # 5. Push file
        if not self._push_settings_file(source):
            return {"success": False, "message": "Failed to push settings file"}

        # 6. Verify
        if not self._verify_file():
            return {"success": False, "message": "Failed to verify file on device"}

        # 7. Start PUBG
        if not self._start_pubg():
            return {"success": False, "message": "Failed to start PUBG"}

        return {"success": True, "message": f"{preset_name} applied successfully"}

    def execute_custom(self, profile_name: str, base64_content: str) -> dict:
        """
        Execute custom profile application from uploaded base64 content
        profile_name: name of the profile
        base64_content: base64 encoded file content
        Returns: {"success": bool, "message": str}
        """
        # 1. Check ADB
        if not self.adb_path.exists():
            return {"success": False, "message": "ADB not found"}

        # 2. Find device
        self._device_id = self._find_gameloop_device()
        if not self._device_id:
            return {"success": False, "message": "Device not connected"}

        # 3. Decode base64
        try:
            file_bytes = base64.b64decode(base64_content.split(',')[1] if ',' in base64_content else base64_content)
            temp_file = self.base_path / f"temp_{profile_name}.sav"
            temp_file.write_bytes(file_bytes)
        except Exception as e:
            return {"success": False, "message": f"Failed to decode file: {e}"}

        # 4. Stop PUBG
        if not self._stop_pubg():
            temp_file.unlink(missing_ok=True)
            return {"success": False, "message": "Failed to stop PUBG"}

        # 5. Push file
        if not self._push_settings_file(temp_file):
            temp_file.unlink(missing_ok=True)
            return {"success": False, "message": "Failed to push settings file"}

        # 6. Verify
        if not self._verify_file():
            temp_file.unlink(missing_ok=True)
            return {"success": False, "message": "Failed to verify file on device"}

        # 7. Start PUBG
        if not self._start_pubg():
            temp_file.unlink(missing_ok=True)
            return {"success": False, "message": "Failed to start PUBG"}

        temp_file.unlink(missing_ok=True)
        return {"success": True, "message": f"{profile_name} applied successfully"}

    def execute_saved_profile(self, profile_name: str, saved_path: str) -> dict:
        """
        Execute a saved profile application from disk
        profile_name: name of the profile
        saved_path: path to saved profile file on disk
        Returns: {"success": bool, "message": str}
        """
        # 1. Check ADB
        if not self.adb_path.exists():
            return {"success": False, "message": "ADB not found"}

        # 2. Find device
        self._device_id = self._find_gameloop_device()
        if not self._device_id:
            return {"success": False, "message": "Device not connected"}

        # 3. Check saved path
        temp_file = Path(saved_path)
        if not temp_file.exists():
            return {"success": False, "message": "Saved profile file not found"}

        # 4. Stop PUBG
        if not self._stop_pubg():
            return {"success": False, "message": "Failed to stop PUBG"}

        # 5. Push file
        if not self._push_settings_file(temp_file):
            return {"success": False, "message": "Failed to push settings file"}

        # 6. Verify
        if not self._verify_file():
            return {"success": False, "message": "Failed to verify file on device"}

        # 7. Start PUBG
        if not self._start_pubg():
            return {"success": False, "message": "Failed to start PUBG"}

        return {"success": True, "message": f"{profile_name} applied successfully"}

    def save_profile(self, name: str, file_name: str, base64_content: str) -> dict:
        """
        Save a profile to disk
        Returns: {"success": bool, "message": str}
        """
        if not name or not name.strip():
            return {"success": False, "message": "Profile name is required"}
        if not base64_content:
            return {"success": False, "message": "File content is required"}

        try:
            profiles = []
            if self.profiles_file.exists():
                with open(self.profiles_file, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)

            # Ensure profiles directory exists
            profiles_dir = self.base_path / 'profiles'
            profiles_dir.mkdir(parents=True, exist_ok=True)

            # Save file content
            file_bytes = base64.b64decode(base64_content.split(',')[1] if ',' in base64_content else base64_content)
            saved_file = profiles_dir / f"{name}.sav"
            saved_file.write_bytes(file_bytes)

            # Add to profiles list
            profiles.append({
                "name": name,
                "file_name": file_name,
                "saved_path": str(saved_file),
                "created": time.time()
            })

            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                json.dump(profiles, f, ensure_ascii=False, indent=2)

            return {"success": True, "message": "Profile saved"}
        except Exception as e:
            return {"success": False, "message": f"Failed to save profile: {e}"}

    def get_profiles(self) -> list:
        """
        Get all saved profiles
        Returns: list of profile dicts
        """
        if not self.profiles_file.exists():
            return []
        try:
            with open(self.profiles_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    def delete_profile(self, index: int) -> dict:
        """
        Delete a profile by index
        Returns: {"success": bool, "message": str}
        """
        try:
            profiles = self.get_profiles()
            if index < 0 or index >= len(profiles):
                return {"success": False, "message": "Invalid profile index"}

            profile = profiles[index]
            saved_path = profile.get("saved_path")
            if saved_path:
                Path(saved_path).unlink(missing_ok=True)

            profiles.pop(index)
            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                json.dump(profiles, f, ensure_ascii=False, indent=2)

            return {"success": True, "message": "Profile deleted"}
        except Exception as e:
            return {"success": False, "message": f"Failed to delete profile: {e}"}

    def exit_app(self):
        """Close the application"""
        try:
            self._run_adb(['kill-server'], timeout=10)
        except:
            pass
        if hasattr(self, 'window') and self.window:
            self.window.destroy()
        return {"success": True}


def get_resource_path(relative_path: str) -> str:
    """
    Get resource path - works in development and in compiled EXE
    """
    if getattr(sys, 'frozen', False):
        base_path = Path(sys.executable).parent
    else:
        base_path = Path(__file__).parent
    return str(base_path / relative_path)


def create_window():
    """Create application window"""
    api = PUBGFPSApi()
    html_path = get_resource_path('index.html')

    window = webview.create_window(
        title='T O M - PUBG FPS Settings',
        url=f"file:///{html_path.replace(os.sep, '/')}",
        js_api=api,
        width=720,
        height=780,
        resizable=False,
        frameless=False,
        easy_drag=True,
        background_color='#020810'
    )

    api.window = window
    webview.start(debug=True)


def main():
    """Application entry point"""
    try:
        create_window()
    except Exception as e:
        print(f"Error running application: {e}")
        input("Press Enter...")
        sys.exit(1)


if __name__ == '__main__':
    main()
