import json
import threading
import time
import traceback

from android_utils import run_on_ui_thread
from base_plugin import BasePlugin, MenuItemData, MenuItemType
from client_utils import get_last_fragment, log
from com.exteragram.messenger.plugins.ui import PluginsActivity, PluginSettingsActivity
from java import dynamic_proxy, jclass
from org.telegram.messenger import ApplicationLoader, NotificationCenter

from features.deeplink import register_deeplink_hook
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
    _sc_menu_label,
    _setting_value_key,
    _shortcut_title,
    _show_bulletin_error,
    _show_bulletin_info,
    _show_bulletin_success,
)
from utils.scanner import (
    _collect_settings,
    _find_setting_item,
    _find_sub_fragment_item,
    _get_item_cb,
    _get_item_click_cb,
    _get_item_text,
    _invoke_click_callback,
    _trigger_setting_on_change,
)


def _clean_corrupted_preferences():
    try:
        context = ApplicationLoader.applicationContext
        if not context:
            return
        pref_names = [
            f"plugin_{__id__}",
            f"plugins_{__id__}",
            f"{__id__}_settings",
            "plugins_settings",
            __id__,
        ]
        for name in pref_names:
            try:
                sp = context.getSharedPreferences(name, 0)
                if sp:
                    all_entries = sp.getAll()
                    if all_entries:
                        editor = sp.edit()
                        has_changes = False
                        for k in all_entries.keySet().toArray():
                            key_str = str(k)
                            val = all_entries.get(k)
                            if val is None or key_str.startswith("__wiz_"):
                                editor.remove(key_str)
                                has_changes = True
                        if has_changes:
                            editor.commit()
            except Exception as e:
                log(f"[{__id__}] clean pref {name}: {e}")
    except Exception as e:
        log(f"[{__id__}] _clean_corrupted_preferences: {e}")


try:
    _clean_corrupted_preferences()
except Exception:
    pass


class SafeSettingsDict(dict):
    def __setitem__(self, key, value):
        if value is None:
            if key in self:
                super().__delitem__(key)
            return
        super().__setitem__(str(key), value)

    def __getitem__(self, key):
        val = super().get(str(key), None)
        return val if val is not None else ""

    def get(self, key, default=""):
        val = super().get(str(key), None)
        if val is not None:
            return val
        return default if default is not None else ""

    def items(self):
        return [(k, v) for k, v in super().items() if k is not None and v is not None and not str(k).startswith("__wiz_")]

    def values(self):
        return [v for k, v in super().items() if k is not None and v is not None and not str(k).startswith("__wiz_")]

    def keys(self):
        return [k for k, v in super().items() if k is not None and v is not None and not str(k).startswith("__wiz_")]


try:
    ObserverDelegate = dynamic_proxy(jclass("org.telegram.messenger.NotificationCenter$NotificationCenterDelegate"))

    class ShortcutsNotificationObserver(ObserverDelegate):
        def __init__(self, plugin):
            super().__init__()
            self.plugin = plugin

        def didReceivedNotification(self, notification_id, account, *args):
            try:
                self.plugin._restore_shortcuts()
            except Exception as e:
                log(f"[{__id__}] notification refresh error: {e}")

except Exception as e:
    log(f"[{__id__}] define ShortcutsNotificationObserver: {e}")
    ShortcutsNotificationObserver = None


class ShortcutsPlugin(BasePlugin):
    def __init__(self):
        self._safe_settings_data = SafeSettingsDict()
        super().__init__()
        self._menu_items = []
        self._deeplink_unhook = None
        self._observer = None
        self._sanitize_settings()

    @property
    def settings(self):
        if not hasattr(self, "_safe_settings_data"):
            self._safe_settings_data = SafeSettingsDict()
        return self._safe_settings_data

    @settings.setter
    def settings(self, value):
        if not hasattr(self, "_safe_settings_data"):
            self._safe_settings_data = SafeSettingsDict()
        self._safe_settings_data.clear()
        if isinstance(value, dict):
            for k, v in value.items():
                if k is not None and v is not None and not str(k).startswith("__wiz_"):
                    self._safe_settings_data[str(k)] = v

    def on_plugin_load(self):
        try:
            self._sanitize_settings()
            self._restore_shortcuts()
            if ShortcutsNotificationObserver is not None:
                try:
                    self._observer = ShortcutsNotificationObserver(self)
                    NotificationCenter.getGlobalInstance().addObserver(self._observer, NotificationCenter.pluginsUpdated)
                    NotificationCenter.getGlobalInstance().addObserver(self._observer, NotificationCenter.pluginSettingsRegistered)
                    NotificationCenter.getGlobalInstance().addObserver(self._observer, NotificationCenter.pluginSettingsUnregistered)
                except Exception as ex:
                    log(f"[{__id__}] addObserver error: {ex}")
            threading.Thread(target=self._register_deeplink_hook_async, daemon=True).start()
        except Exception as e:
            log(f"[{__id__}] on_plugin_load: {e}")

    def _sanitize_settings(self):
        try:
            _clean_corrupted_preferences()
            if hasattr(self, "_safe_settings_data") and isinstance(self._safe_settings_data, dict):
                for k in list(self._safe_settings_data.keys()):
                    if self._safe_settings_data[k] is None or str(k).startswith("__wiz_"):
                        del self._safe_settings_data[k]
        except Exception as e:
            log(f"[{__id__}] _sanitize_settings error: {e}")

    def get_setting(self, key, default=""):
        val = self.settings.get(key, None)
        if val is not None and val != "":
            return val
        try:
            val = super().get_setting(key, default)
            if val is not None:
                self.settings[str(key)] = val
                return val
        except Exception:
            pass
        return default if default is not None else ""

    def set_setting(self, key, value, reload_settings=False):
        if value is None:
            if key in self.settings:
                del self.settings[key]
            return
        self.settings[str(key)] = value
        try:
            super().set_setting(key, value)
        except Exception as e:
            log(f"[{__id__}] super().set_setting error: {e}")

    def getAllSettings(self):
        self._sanitize_settings()
        return dict(self.settings.items())

    def get_all_settings(self):
        return self.getAllSettings()

    def getSettings(self):
        return self.getAllSettings()

    def get_settings(self):
        return self.getAllSettings()

    def getPluginSettings(self):
        return self.getAllSettings()

    def _register_deeplink_hook_async(self):
        try:
            self._deeplink_unhook = register_deeplink_hook(self)
        except Exception as e:
            log(f"[{__id__}] async deeplink hook: {e}")

    def on_plugin_unload(self):
        self._clear_menu_items()
        if hasattr(self, "_observer") and self._observer is not None:
            try:
                NotificationCenter.getGlobalInstance().removeObserver(self._observer, NotificationCenter.pluginsUpdated)
                NotificationCenter.getGlobalInstance().removeObserver(self._observer, NotificationCenter.pluginSettingsRegistered)
                NotificationCenter.getGlobalInstance().removeObserver(self._observer, NotificationCenter.pluginSettingsUnregistered)
            except Exception:
                pass
            self._observer = None
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
            self._sanitize_settings()
            return build_settings_list(self)
        except Exception as e:
            log(f"[{__id__}] create_settings: {e}\n{traceback.format_exc()}")
            return [Header(text=_s("shortcuts")), Divider(text=str(e))]

    # ========== EXECUTION ==========
    def _exec_shortcut(self, sc):
        t = sc.get("type", "toggle_plugin")
        pid = sc.get("plugin_id", "")

        if not _plugin_exists(pid):
            _show_bulletin_error(f"{pid}: {_s('plugin_not_found')}")
            return

        if t == "toggle_plugin":
            plugin = _ctrl().plugins.get(pid)
            if plugin:
                self._toggle(pid, _plugin_name(pid), not bool(plugin.isEnabled()))

        elif t == "open_settings":
            sub = sc.get("sub_fragment", "")
            self._open_settings_or_subfragment(pid, sub_fragment=sub)

        elif t == "operate_setting":

            def _do_operate():
                try:
                    st = sc.get("setting_type", "switch")
                    vk = _setting_value_key(sc)

                    setting_found = False
                    try:
                        for setting in _collect_settings(pid, ensure_loaded=True):
                            if _setting_value_key(setting) == vk:
                                setting_found = True
                                break
                    except Exception as e:
                        log(f"[{__id__}] check setting exists {pid}: {e}")

                    if not setting_found:
                        _show_bulletin_error(_s("setting_not_found"))
                        return

                    if st == "switch":
                        try:
                            cur = _ctrl().getPluginSettingBoolean(pid, vk, False)
                        except Exception:
                            cur = False
                        value = not bool(cur)
                        _ctrl().setPluginSetting(pid, vk, value)
                        _trigger_setting_on_change(pid, sc, value)
                        self._restore_shortcuts()
                        try:
                            _ctrl().loadPluginSettings(__id__)
                        except Exception:
                            pass
                        _show_bulletin_success(f"{_plugin_name(pid)}: {('ON' if value else 'OFF')}")
                    elif st == "selector":
                        opts = sc.get("setting_items") or sc.get("items") or []
                        if not opts:
                            try:
                                for setting in _collect_settings(pid, ensure_loaded=False):
                                    if _setting_value_key(setting) == vk:
                                        opts = setting.get("items") or []
                                        break
                            except Exception as e:
                                log(f"[{__id__}] selector items fallback: {e}")
                        show_selector_dialog(self, pid, vk, _shortcut_title(sc), opts, sc)
                    elif st == "input":
                        show_input_dialog(self, pid, vk, _shortcut_title(sc), sc)
                    elif st in ("button", "action"):
                        item = _find_setting_item(pid, sc)
                        click_cb = _get_item_click_cb(item) if item else None
                        if click_cb is not None:

                            def _run_click():
                                try:
                                    _invoke_click_callback(click_cb)
                                except Exception as e:
                                    log(f"[{__id__}] button click error {pid}:{vk}: {e}")

                            run_on_ui_thread(_run_click)
                            _show_bulletin_success(f"{_plugin_name(pid)}: {_sc_label(sc)}")
                        else:
                            _show_bulletin_error(_s("setting_not_found"))
                except Exception as e:
                    log(f"[{__id__}] operate_setting error: {e}")

            threading.Thread(target=_do_operate, daemon=True).start()

    def _toggle(self, pid, pname, enabled):
        def _do():
            try:
                CallbackClass = jclass("org.telegram.messenger.Utilities$Callback")
                Callback = dynamic_proxy(CallbackClass)

                class ToggleCb(Callback):
                    def __init__(self, plugin_ref):
                        super().__init__()
                        self.plugin_ref = plugin_ref

                    def run(self, err):
                        self.plugin_ref._restore_shortcuts()
                        try:
                            _ctrl().loadPluginSettings(__id__)
                        except Exception:
                            pass
                        if err:
                            _show_bulletin_error(str(err))
                        else:
                            msg = f"{pname}: ON" if enabled else f"{pname}: OFF"
                            _show_bulletin_success(msg)

                _ctrl().setPluginEnabled(pid, enabled, ToggleCb(self))
            except Exception as e:
                log(f"[{__id__}] toggle callback error: {e}")
                try:
                    _ctrl().setPluginEnabled(pid, enabled, None)
                    time.sleep(0.15)
                    self._restore_shortcuts()
                    try:
                        _ctrl().loadPluginSettings(__id__)
                    except Exception:
                        pass
                    msg = f"{pname}: ON" if enabled else f"{pname}: OFF"
                    _show_bulletin_success(msg)
                except Exception as ex:
                    log(f"[{__id__}] toggle fallback error: {ex}")
                    _show_bulletin_error(str(ex))

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
                    _show_bulletin_info(f"{plugin.getName()}: {_s('plugin_disabled_open_manager')}")
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
                    try:
                        item = _find_sub_fragment_item(pid, sub_fragment)
                        cb = _get_item_cb(item) if item else None
                        title = _get_item_text(item) if item else ""
                        if cb is not None:
                            frag.presentFragment(PluginSettingsActivity(plugin, str(title), None, cb))
                            return
                    except Exception as e:
                        log(f"[{__id__}] open_settings sub_fragment find {pid}: {e}")

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
            raw = []
        normalized = []
        has_system = False
        for sc in raw:
            if not isinstance(sc, dict):
                continue
            if sc.get("is_system"):
                has_system = True
                label_val = str(sc.get("label", "") or "").strip()
                if not label_val or label_val == "shortcuts":
                    sc = dict(sc)
                    sc["label"] = _s("shortcuts")
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

        if not has_system:
            system_sc = {
                "type": "open_settings",
                "plugin_id": __id__,
                "location": "drawer",
                "locations": ["drawer"],
                "label": _s("shortcuts"),
                "icon": "media_settings",
                "is_system": True,
            }
            normalized.insert(0, system_sc)
            self._save_shortcuts(normalized)

        return normalized

    def _save_shortcuts(self, sc_list):
        self.set_setting("shortcuts_json", json.dumps(sc_list, ensure_ascii=False))

    def _restore_shortcuts(self):
        self._clear_menu_items()
        shortcuts = self._load_shortcuts()
        for i, sc in enumerate(shortcuts):
            try:
                priority = max(1, 100 - i)
                self._register_menu(sc, priority=priority)
            except Exception as e:
                log(f"[{__id__}] restore shortcut: {e}")

    def _clear_menu_items(self):
        for mid in self._menu_items:
            _remove_menu_item_safe(self, mid)
        self._menu_items = []

    def _register_menu(self, sc, priority=10):
        label, subtext = _sc_menu_label(sc)
        icon = sc.get("icon") or "media_settings"
        menu_type_by_location = {
            "drawer": MenuItemType.DRAWER_MENU,
            "chat": MenuItemType.CHAT_ACTION_MENU,
            "message": MenuItemType.MESSAGE_CONTEXT_MENU,
            "profile": MenuItemType.PROFILE_ACTION_MENU,
        }
        menu_types = [menu_type_by_location[location] for location in _sc_locations(sc)]
        for mt in menu_types:
            mid = self.add_menu_item(
                MenuItemData(
                    menu_type=mt,
                    text=label,
                    subtext=subtext,
                    icon=icon,
                    priority=priority,
                    on_click=lambda ctx, _sc=sc: self._exec_shortcut(_sc),
                )
            )
            if mid:
                self._menu_items.append(mid)

    def _move_shortcut(self, idx, direction):
        sc_list = self._load_shortcuts()
        target_idx = idx + direction
        if 0 <= idx < len(sc_list) and 0 <= target_idx < len(sc_list):
            if sc_list[idx].get("is_system") or sc_list[target_idx].get("is_system"):
                return
            sc_list[idx], sc_list[target_idx] = sc_list[target_idx], sc_list[idx]
            self._save_shortcuts(sc_list)
            self._restore_shortcuts()
            _show_bulletin_success(_s("shortcut_reordered"))
            try:
                _ctrl().loadPluginSettings(__id__)
            except Exception as e:
                log(f"[{__id__}] move reload error: {e}")

    def _remove_shortcut(self, idx):
        sc_list = self._load_shortcuts()
        if 0 <= idx < len(sc_list):
            if sc_list[idx].get("is_system"):
                _show_bulletin_error(_s("cannot_remove_system"))
                return
            removed = sc_list.pop(idx)
            self._save_shortcuts(sc_list)
            self._restore_shortcuts()
            _show_bulletin_success(f"{_s('shortcut_removed')}: {_sc_label(removed)}")
            try:
                _ctrl().loadPluginSettings(__id__)
            except Exception as e:
                log(f"[{__id__}] remove reload error: {e}")
