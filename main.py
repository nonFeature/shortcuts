import json
import threading
import traceback

from android_utils import run_on_ui_thread
from base_plugin import BasePlugin, MenuItemData, MenuItemType
from client_utils import get_last_fragment, log
from com.exteragram.messenger.plugins.ui import PluginsActivity, PluginSettingsActivity
from ui.bulletin import BulletinHelper

from features.deeplink import register_deeplink_hook
from features.quick_access import update_quick_access
from header import __id__
from i18n.locales import _s
from ui.settings import Divider, Header, build_settings_list, show_input_dialog, show_selector_dialog
from utils.helpers import (
    _ctrl,
    _plugin_exists,
    _plugin_name,
    _remove_menu_item_safe,
    _sc_label,
    _sc_locations,
    _setting_value_key,
    _shortcut_title,
)
from utils.scanner import _collect_settings, _trigger_setting_on_change


class ShortcutsPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self._menu_items = []
        self._qa_mid = None
        self._deeplink_unhook = None

    def on_plugin_load(self):
        try:
            if bool(self.get_setting("auto_remove_missing", False)):
                self._cleanup_missing_shortcuts(restore_menus=False, notify=False)
            self._restore_shortcuts()
            update_quick_access(self)
            threading.Thread(target=self._register_deeplink_hook_async, daemon=True).start()
        except Exception as e:
            log(f"[{__id__}] on_plugin_load: {e}")

    def _register_deeplink_hook_async(self):
        try:
            self._deeplink_unhook = register_deeplink_hook(self)
        except Exception as e:
            log(f"[{__id__}] async deeplink hook: {e}")

    def on_plugin_unload(self):
        self._clear_menu_items()
        _remove_menu_item_safe(self, self._qa_mid)
        self._qa_mid = None
        if self._deeplink_unhook:
            try:
                if isinstance(self._deeplink_unhook, list):
                    for u in self._deeplink_unhook:
                        if hasattr(u, "unhook"):
                            u.unhook()
                elif hasattr(self._deeplink_unhook, "unhook"):
                    self._deeplink_unhook.unhook()
            except Exception:
                pass
            self._deeplink_unhook = None

    def create_settings(self):
        try:
            return build_settings_list(self)
        except Exception as e:
            log(f"[{__id__}] create_settings: {e}\n{traceback.format_exc()}")
            return [Header(text=_s("shortcuts")), Divider(text=str(e))]

    def _on_auto_remove_missing_toggle(self, enabled):
        if enabled:
            self._cleanup_missing_shortcuts(restore_menus=True, notify=True)

    def _cleanup_missing_shortcuts(self, restore_menus=True, notify=False):
        sc_list = self._load_shortcuts()
        filtered = [sc for sc in sc_list if _plugin_exists(sc.get("plugin_id", ""))]
        removed = len(sc_list) - len(filtered)
        if removed <= 0:
            return 0
        self._save_shortcuts(filtered)
        if restore_menus:
            self._restore_shortcuts()
        if notify:
            run_on_ui_thread(lambda: BulletinHelper.show_success(f"{_s('missing_shortcuts_removed')}: {removed}"))
        return removed

    def _open_self_settings(self):
        def _do():
            try:
                plugin = _ctrl().plugins.get(__id__)
                if plugin:
                    frag = get_last_fragment()
                    if frag:
                        frag.presentFragment(PluginSettingsActivity(plugin))
            except Exception as e:
                log(f"[{__id__}] _open_self_settings: {e}")

        run_on_ui_thread(_do)

    # ========== EXECUTION ==========
    def _exec_shortcut(self, sc):
        t = sc.get("type", "toggle_plugin")
        pid = sc.get("plugin_id", "")

        if not _plugin_exists(pid):
            if bool(self.get_setting("auto_remove_missing", False)):
                self._cleanup_missing_shortcuts(restore_menus=True, notify=False)
            run_on_ui_thread(lambda: BulletinHelper.show_error(f"{pid}: {_s('plugin_not_found')}"))
            return

        if t == "toggle_plugin":
            plugin = _ctrl().plugins.get(pid)
            if plugin:
                self._toggle(pid, _plugin_name(pid), not bool(plugin.isEnabled()))

        elif t == "open_settings":
            sub = sc.get("sub_fragment", "")
            self._open_settings_or_subfragment(pid, sub_fragment=sub)

        elif t == "operate_setting":
            st = sc.get("setting_type", "switch")
            vk = _setting_value_key(sc)

            if st == "switch":
                try:
                    cur = _ctrl().getPluginSettingBoolean(pid, vk, False)
                except Exception:
                    cur = False
                value = not bool(cur)
                _ctrl().setPluginSetting(pid, vk, value)
                _trigger_setting_on_change(pid, sc, value)
                run_on_ui_thread(lambda: BulletinHelper.show_success(f"{_plugin_name(pid)}: {('ON' if value else 'OFF')}"))
            elif st == "selector":
                opts = sc.get("setting_items") or sc.get("items") or []
                if not opts:
                    try:
                        for setting in _collect_settings(pid):
                            if _setting_value_key(setting) == vk:
                                opts = setting.get("items") or []
                                break
                    except Exception as e:
                        log(f"[{__id__}] selector items fallback: {e}")
                show_selector_dialog(self, pid, vk, _shortcut_title(sc), opts, sc)
            elif st == "input":
                show_input_dialog(self, pid, vk, _shortcut_title(sc), sc)

    def _toggle(self, pid, pname, enabled):
        def _do():
            try:
                _ctrl().setPluginEnabled(pid, enabled, None)
                msg = f"{pname}: ON" if enabled else f"{pname}: OFF"
                run_on_ui_thread(lambda: BulletinHelper.show_success(msg))
            except Exception as e:
                log(f"[{__id__}] toggle {pid}: {e}")
                err_msg = str(e)
                run_on_ui_thread(lambda: BulletinHelper.show_error(err_msg))

        import threading

        threading.Thread(target=_do, daemon=True).start()

    def _open_settings_or_subfragment(self, pid, sub_fragment=None):
        def _do():
            try:
                frag = get_last_fragment()
                if not frag:
                    return

                ctrl = _ctrl()
                plugin = ctrl.plugins.get(pid)
                if not plugin:
                    return
                if not plugin.isEnabled():
                    run_on_ui_thread(lambda: BulletinHelper.show_info(f"{plugin.getName()}: {_s('plugin_disabled_open_manager')}"))
                    try:
                        frag.presentFragment(PluginsActivity())
                    except Exception as e:
                        log(f"[{__id__}] open_settings disabled fallback {pid}: {e}")
                    return
                try:
                    ctrl.loadPluginSettings(pid)
                except Exception as e:
                    log(f"[{__id__}] open_settings preload {pid}: {e}")

                eng = ctrl.getPluginEngine(pid)
                if sub_fragment:
                    if eng:
                        try:
                            eng.openPluginSetting(pid, sub_fragment, frag)
                            return
                        except Exception:
                            pass
                    frag.presentFragment(PluginSettingsActivity(plugin, sub_fragment))
                else:
                    if eng:
                        try:
                            eng.openPluginSettings(pid, frag)
                            return
                        except Exception:
                            pass
                    frag.presentFragment(PluginSettingsActivity(plugin))
            except Exception as e:
                log(f"[{__id__}] open_settings_or_subfragment {pid}: {e}")

        run_on_ui_thread(_do)

    # ========== SHORTCUTS MANAGEMENT ==========
    def _load_shortcuts(self):
        try:
            raw = json.loads(self.get_setting("shortcuts_json", "[]"))
        except Exception:
            return []
        if isinstance(raw, dict):
            items = raw.get("items")
            if isinstance(items, list):
                raw = items
            else:
                legacy_items = raw.get("shortcuts")
                raw = legacy_items if isinstance(legacy_items, list) else []
        if not isinstance(raw, list):
            return []
        normalized = []
        for sc in raw:
            if not isinstance(sc, dict):
                continue
            if sc.get("type") == "operate_setting" and isinstance(sc.get("setting"), dict):
                ref = sc.get("setting") or {}
                merged = dict(sc)
                merged["setting_key"] = merged.get("setting_key", ref.get("key", ""))
                merged["setting_value_key"] = merged.get("setting_value_key", ref.get("value_key", ref.get("key", "")))
                merged["setting_open_key"] = merged.get("setting_open_key", ref.get("open_key", merged["setting_key"]))
                merged["setting_type"] = merged.get("setting_type", ref.get("type", "switch"))
                normalized.append(merged)
                continue
            normalized.append(sc)
        return normalized

    def _save_shortcuts(self, sc_list):
        self.set_setting("shortcuts_json", json.dumps(sc_list, ensure_ascii=False))

    def _restore_shortcuts(self):
        self._clear_menu_items()
        for sc in self._load_shortcuts():
            try:
                self._register_menu(sc)
            except Exception as e:
                log(f"[{__id__}] restore shortcut: {e}")

    def _clear_menu_items(self):
        for mid in self._menu_items:
            _remove_menu_item_safe(self, mid)
        self._menu_items = []

    def _register_menu(self, sc):
        label = str(sc.get("label") or _sc_label(sc))[:50]
        icon = sc.get("icon") or "media_settings"
        menu_type_by_location = {
            "drawer": MenuItemType.DRAWER_MENU,
            "chat": MenuItemType.CHAT_ACTION_MENU,
            "message": MenuItemType.MESSAGE_CONTEXT_MENU,
            "profile": MenuItemType.PROFILE_ACTION_MENU,
        }
        menu_types = [menu_type_by_location[location] for location in _sc_locations(sc)]
        for mt in menu_types:
            mid = self.add_menu_item(MenuItemData(menu_type=mt, text=label, icon=icon, priority=10, on_click=lambda ctx, _sc=sc: self._exec_shortcut(_sc)))
            if mid:
                self._menu_items.append(mid)

    def _remove_shortcut(self, idx):
        sc_list = self._load_shortcuts()
        if 0 <= idx < len(sc_list):
            sc_list.pop(idx)
            self._save_shortcuts(sc_list)
            self._restore_shortcuts()

            def _finish_action_fragment():
                try:
                    fragment = get_last_fragment()
                    if fragment:
                        fragment.finishFragment()
                except Exception as e:
                    log(f"[{__id__}] close removed shortcut fragment: {e}")

            run_on_ui_thread(lambda: BulletinHelper.show_success(_s("shortcut_removed")))
            run_on_ui_thread(_finish_action_fragment)
            _ctrl().loadPluginSettings(__id__)
