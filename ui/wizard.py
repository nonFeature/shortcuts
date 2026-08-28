import threading
import time
import traceback

from client_utils import get_last_fragment, log
from org.telegram.messenger import ApplicationLoader

from data.constants import PRESET_ICONS
from header import __id__
from i18n.locales import _s
from ui.settings import Divider, Header, Input, Selector, Switch, Text
from utils.helpers import (
    _ctrl,
    _finish_and_show_success,
    _plugin_name,
    _sc_label,
    _sc_locations,
    _setting_value_key,
    _show_bulletin_error,
    _show_bulletin_success,
)
from utils.scanner import _collect_settings, _collect_sub_fragments, _has_settings_reliably, _plugin_ids

LOCATION_KEYS = ("drawer", "chat", "message", "profile")


def _init_new_wizard_state(plugin, pids):
    selected_pid = pids[0] if pids else ""
    for location_key in LOCATION_KEYS:
        plugin.set_setting(f"__wiz_loc_{location_key}_{WIZ_SESSION}", location_key == "drawer")
    plugin.set_setting(f"__wiz_plugin_{WIZ_SESSION}", 0)
    plugin.set_setting(f"__wiz_type_{WIZ_SESSION}", 0)
    plugin.set_setting(f"__wiz_subfragment_{WIZ_SESSION}", 0)
    plugin.set_setting(f"__wiz_setting_{WIZ_SESSION}", 0)
    plugin.set_setting(f"__wiz_label_{WIZ_SESSION}", str(_plugin_name(selected_pid) if selected_pid else "")[:50])
    plugin.set_setting(f"__wiz_icon_{WIZ_SESSION}", "media_settings")
    plugin.set_setting(f"__wiz_custom_icon_{WIZ_SESSION}", "")


def _init_edit_wizard_state(plugin, edit_index, pids):
    shortcuts = plugin._load_shortcuts()
    if not (0 <= edit_index < len(shortcuts)):
        return
    sc = shortcuts[edit_index]
    pid = sc.get("plugin_id", "")
    try:
        plugin_index = pids.index(pid)
    except ValueError:
        plugin_index = 0
    locations = set(_sc_locations(sc))
    type_index = {"toggle_plugin": 0, "open_settings": 1, "operate_setting": 2}.get(sc.get("type"), 0)
    for location_key in LOCATION_KEYS:
        plugin.set_setting(f"__wiz_loc_{location_key}_{WIZ_SESSION}", location_key in locations)
    plugin.set_setting(f"__wiz_plugin_{WIZ_SESSION}", plugin_index)
    plugin.set_setting(f"__wiz_type_{WIZ_SESSION}", type_index)
    raw_label = str(sc.get("label", "") or "").strip()
    if not raw_label:
        raw_label = _s("shortcuts") if sc.get("is_system") or pid == __id__ else _plugin_name(pid)
    plugin.set_setting(f"__wiz_label_{WIZ_SESSION}", raw_label[:50])
    plugin.set_setting(f"__wiz_icon_{WIZ_SESSION}", str(sc.get("icon", "media_settings") or "media_settings"))
    plugin.set_setting(f"__wiz_custom_icon_{WIZ_SESSION}", "")

    if sc.get("type") == "open_settings":
        subs = _collect_sub_fragments(pid, ensure_loaded=False)
        sub_keys = ["root"] + [s["key"] for s in subs]
        plugin.set_setting(f"__wiz_subfragment_{WIZ_SESSION}", _edit_subfragment_index(sc, sub_keys))
    else:
        plugin.set_setting(f"__wiz_subfragment_{WIZ_SESSION}", 0)

    if sc.get("type") == "operate_setting":
        settings = _collect_settings(pid, ensure_loaded=False)
        plugin.set_setting(f"__wiz_setting_{WIZ_SESSION}", _edit_setting_index(sc, settings))
    else:
        plugin.set_setting(f"__wiz_setting_{WIZ_SESSION}", 0)


WIZ_SESSION = ""


def _clean_wizard_cache(plugin, keep_session=None):
    try:
        context = ApplicationLoader.applicationContext
        if context:
            pref_names = [f"plugin_{__id__}", f"plugins_{__id__}", f"{__id__}_settings", __id__]
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
                                if key_str.startswith("__wiz_"):
                                    if keep_session and key_str.endswith(f"_{keep_session}"):
                                        continue
                                    editor.remove(key_str)
                                    has_changes = True
                            if has_changes:
                                editor.commit()
                except Exception:
                    pass
    except Exception as e:
        log(f"[{__id__}] _clean_wizard_cache: {e}")
    try:
        if hasattr(plugin, "settings") and isinstance(plugin.settings, dict):
            for k in list(plugin.settings.keys()):
                key_str = str(k)
                if key_str.startswith("__wiz_"):
                    if keep_session and key_str.endswith(f"_{keep_session}"):
                        continue
                    del plugin.settings[k]
    except Exception:
        pass


def build_new_wizard(plugin):
    initialized = False

    def _render():
        nonlocal initialized
        pids = _plugin_ids()
        if not initialized:
            global WIZ_SESSION
            import time

            WIZ_SESSION = str(int(time.time() * 1000))
            _clean_wizard_cache(plugin, keep_session=WIZ_SESSION)
            _init_new_wizard_state(plugin, pids)
            initialized = True
        return _render_wizard(plugin, pids, edit_index=None)

    return _render


def build_wizard_step1(plugin, edit_index=None):
    initialized = False

    def _render():
        nonlocal initialized
        pids = _plugin_ids()
        if not initialized:
            global WIZ_SESSION
            import time

            WIZ_SESSION = str(int(time.time() * 1000))
            _clean_wizard_cache(plugin, keep_session=WIZ_SESSION)
            if edit_index is not None:
                _init_edit_wizard_state(plugin, edit_index, pids)
            else:
                _init_new_wizard_state(plugin, pids)
            initialized = True
        return _render_wizard(plugin, pids, edit_index=edit_index)

    return _render


def _render_wizard(plugin, pids, edit_index=None):
    def _build():
        ctrl = _ctrl()
        editing_sc = None
        if edit_index is not None:
            shortcuts = plugin._load_shortcuts()
            if 0 <= edit_index < len(shortcuts):
                editing_sc = shortcuts[edit_index]

        items = [
            Switch(
                key=f"__wiz_loc_{key}_{WIZ_SESSION}",
                text=_s(label_key),
                default=ctrl.getPluginSettingBoolean(__id__, f"__wiz_loc_{key}_{WIZ_SESSION}", False),
            )
            for key, label_key in (
                ("drawer", "drawer"),
                ("chat", "chat_menu"),
                ("message", "message_menu"),
                ("profile", "profile_menu"),
            )
        ]
        items.append(Divider(text=_s("location_hint")))

        if editing_sc and editing_sc.get("is_system"):
            items.append(Divider())
            items.extend(build_wizard_step_customize(plugin, pids, editing_sc.get("type"), edit_index=edit_index))
            return items

        if not pids:
            return [*items, Divider(text=_s("no_plugins"))]

        try:
            plug_i = ctrl.getPluginSettingInt(__id__, f"__wiz_plugin_{WIZ_SESSION}", 0)
        except Exception:
            plug_i = 0
        if plug_i < 0 or plug_i >= len(pids):
            plug_i = 0
        selected_pid = pids[plug_i]

        items.append(
            Selector(
                key=f"__wiz_plugin_{WIZ_SESSION}",
                text=_s("plugins"),
                items=[_plugin_name(pid) for pid in pids],
                default=plug_i,
                on_change=lambda value: _on_plugin_change(plugin, value, pids),
            )
        )
        items.append(Divider())

        if not _has_settings_reliably(selected_pid):
            items.append(Divider(text=_s("toggle_only_warning")))
            items.append(Divider())
            items.extend(build_wizard_step_customize(plugin, pids, "toggle_plugin", edit_index=edit_index))
            return items

        try:
            type_i = ctrl.getPluginSettingInt(__id__, f"__wiz_type_{WIZ_SESSION}", 0)
        except Exception:
            type_i = 0
        if type_i < 0 or type_i > 2:
            type_i = 0

        items.append(
            Selector(
                key=f"__wiz_type_{WIZ_SESSION}",
                text=_s("type"),
                items=[_s("toggle_plugin"), _s("open_settings"), _s("operate_setting")],
                default=type_i,
                on_change=lambda value: _on_type_change(plugin, value, pids, selected_pid),
            )
        )

        if type_i == 1:
            sub_keys = ["root"]
            subs = _collect_sub_fragments(selected_pid, ensure_loaded=False)
            if subs:
                sub_titles = [_s("root_settings")]
                for sub in subs:
                    sub_keys.append(sub["key"])
                    sub_titles.append(sub["text"])
                try:
                    sub_default = ctrl.getPluginSettingInt(__id__, f"__wiz_subfragment_{WIZ_SESSION}", 0)
                except Exception:
                    sub_default = 0
                if sub_default < 0 or sub_default >= len(sub_titles):
                    sub_default = 0
                items.append(Selector(key=f"__wiz_subfragment_{WIZ_SESSION}", text=_s("sub_fragment"), items=sub_titles, default=sub_default))
            items.append(Divider())
            items.extend(build_wizard_step_customize(plugin, pids, "open_settings", sub_keys=sub_keys, edit_index=edit_index))
        elif type_i == 2:
            settings = _collect_settings(selected_pid, ensure_loaded=False)
            if not settings:
                items.append(Divider(text=_s("no_settings")))
                items.append(Divider())
                items.extend(build_wizard_step_customize(plugin, pids, "operate_setting", settings=[], edit_index=edit_index))
            else:
                names = [s.get("text", s.get("key", "")) for s in settings]
                try:
                    setting_default = ctrl.getPluginSettingInt(__id__, f"__wiz_setting_{WIZ_SESSION}", 0)
                except Exception:
                    setting_default = 0
                if setting_default < 0 or setting_default >= len(names):
                    setting_default = 0
                items.append(Selector(key=f"__wiz_setting_{WIZ_SESSION}", text=_s("select_setting"), items=names, default=setting_default))
                items.append(Divider())
                items.extend(build_wizard_step_customize(plugin, pids, "operate_setting", settings=settings, edit_index=edit_index))
        else:
            items.append(Divider())
            items.extend(build_wizard_step_customize(plugin, pids, "toggle_plugin", edit_index=edit_index))

        return items

    try:
        return _build()
    except Exception as e:
        err_msg = f"{e}\n{traceback.format_exc()}"
        log(f"[{__id__}] build_wizard_step1 error: {err_msg}")
        return [Header(text=_s("add_shortcut")), Divider(text=f"{_s('error')}: {e!s}")]


def _on_type_change(plugin, value, pids, selected_pid):
    try:
        type_i = int(value)
        plugin.set_setting(f"__wiz_type_{WIZ_SESSION}", type_i)
        plugin.set_setting(f"__wiz_subfragment_{WIZ_SESSION}", 0)
        plugin.set_setting(f"__wiz_setting_{WIZ_SESSION}", 0)
        if selected_pid:
            _ctrl().loadPluginSettings(selected_pid)
        _ctrl().loadPluginSettings(__id__)
    except Exception as e:
        log(f"[{__id__}] type change error: {e}")


def _on_plugin_change(plugin, value, pids):
    try:
        index = int(value)
        last_index = _ctrl().getPluginSettingInt(__id__, f"__wiz_last_plugin_{WIZ_SESSION}", -1)
        if index == last_index:
            return

        if 0 <= index < len(pids):
            pid = pids[index]
            plugin.set_setting(f"__wiz_last_plugin_{WIZ_SESSION}", index)
            plugin.set_setting(f"__wiz_label_{WIZ_SESSION}", str(_plugin_name(pid))[:50])
            plugin.set_setting(f"__wiz_type_{WIZ_SESSION}", 0)
            plugin.set_setting(f"__wiz_subfragment_{WIZ_SESSION}", 0)
            plugin.set_setting(f"__wiz_setting_{WIZ_SESSION}", 0)
            _ctrl().loadPluginSettings(pid)
            _ctrl().loadPluginSettings(__id__)
    except Exception as e:
        log(f"[{__id__}] plugin selection error: {e}")


def build_wizard_step_customize(plugin, pids, stype, sub_keys=None, settings=None, edit_index=None):
    items = []
    try:
        plug_i = _ctrl().getPluginSettingInt(__id__, f"__wiz_plugin_{WIZ_SESSION}", 0)
    except Exception:
        plug_i = 0
    if plug_i < 0 or plug_i >= len(pids):
        plug_i = 0
    pid = pids[plug_i]
    saved_label = _get_setting_string(f"__wiz_label_{WIZ_SESSION}")

    fallback = _s("shortcuts") if edit_index is not None and plugin._load_shortcuts()[edit_index].get("is_system") else _plugin_name(pid)
    def_label = str(saved_label if saved_label else fallback)[:50]

    items.append(Input(key=f"__wiz_label_{WIZ_SESSION}", text=_s("custom_label"), default=def_label))

    icon_key = _selected_icon_key()
    items.append(
        Text(
            text=_s("custom_icon"),
            icon=icon_key,
            create_sub_fragment=lambda: build_icon_picker(plugin),
        )
    )

    items.append(Divider())
    action_key = "save" if edit_index is not None else "create"
    items.append(
        Text(
            text=_s(action_key),
            accent=True,
            on_click=lambda v: wizard_finalize(plugin, pids, stype, sub_keys=sub_keys, settings=settings, edit_index=edit_index),
        )
    )
    return items


def wizard_finalize(plugin, pids, stype, sub_keys=None, settings=None, edit_index=None):
    wizard_fragment = get_last_fragment()

    def _do():
        try:
            ctrl = _ctrl()
            locations = [key for key in LOCATION_KEYS if ctrl.getPluginSettingBoolean(__id__, f"__wiz_loc_{key}_{WIZ_SESSION}", False)]

            sc_list = plugin._load_shortcuts()
            is_sys = False
            if edit_index is not None and 0 <= edit_index < len(sc_list):
                is_sys = bool(sc_list[edit_index].get("is_system"))

            if not locations and not is_sys:
                _show_bulletin_error(_s("location_required"))
                return
            plug_i = ctrl.getPluginSettingInt(__id__, f"__wiz_plugin_{WIZ_SESSION}", 0)
            custom_label = str(ctrl.getPluginSettingString(__id__, f"__wiz_label_{WIZ_SESSION}", "") or "").strip()[:50]

            legacy_location = "both" if locations == ["drawer", "chat"] else (locations[0] if locations else "")
            if plug_i < 0 or plug_i >= len(pids):
                plug_i = 0
            pid = pids[plug_i]

            icon_key = _selected_icon_key()
            if not _icon_exists(icon_key):
                _show_bulletin_error(_s("icon_not_found"))
                return

            if not custom_label:
                if is_sys or pid == __id__:
                    custom_label = _s("shortcuts")
                else:
                    custom_label = _plugin_name(pid)[:50]

            if edit_index is not None and 0 <= edit_index < len(sc_list):
                sc = dict(sc_list[edit_index])
                for key in ("sub_fragment", "setting_key", "setting_value_key", "setting_open_key", "setting_type", "setting_items"):
                    sc.pop(key, None)

                if sc.get("is_system"):
                    # Preserve original type and pid for system shortcuts
                    sc.update({"location": legacy_location, "locations": locations, "label": custom_label, "icon": icon_key})
                else:
                    sc.update({"type": stype, "plugin_id": pid, "location": legacy_location, "locations": locations, "label": custom_label, "icon": icon_key})
            else:
                sc = {"type": stype, "plugin_id": pid, "location": legacy_location, "locations": locations, "label": custom_label, "icon": icon_key}

            if stype == "open_settings" and sub_keys:
                sub_i = ctrl.getPluginSettingInt(__id__, f"__wiz_subfragment_{WIZ_SESSION}", 0)
                if 0 <= sub_i < len(sub_keys):
                    sub = sub_keys[sub_i]
                    if sub != "root":
                        sc["sub_fragment"] = sub

            elif stype == "operate_setting" and settings:
                set_i = ctrl.getPluginSettingInt(__id__, f"__wiz_setting_{WIZ_SESSION}", 0)
                if 0 <= set_i < len(settings):
                    sel = settings[set_i]
                    st = sel.get("type")
                    vk = _setting_value_key(sel)
                    sc["setting_key"] = sel.get("key")
                    sc["setting_value_key"] = vk
                    sc["setting_open_key"] = sel.get("open_key", sel.get("key"))
                    sc["setting_type"] = st
                    if st == "selector":
                        sc["setting_items"] = sel.get("items") or []

            if edit_index is not None and 0 <= edit_index < len(sc_list):
                sc_list[edit_index] = sc
            else:
                sc_list.append(sc)
            plugin._save_shortcuts(sc_list)
            if edit_index is not None and 0 <= edit_index < len(sc_list):
                plugin._restore_shortcuts()
            else:
                plugin._register_menu(sc)

            label = _sc_label(sc)
            message_key = "shortcut_updated" if edit_index is not None else "shortcut_created"
            _finish_and_show_success(wizard_fragment, f"{_s(message_key)}: {label}")
            threading.Thread(target=lambda: _reload_settings_after_wizard(ctrl), daemon=True).start()
        except Exception as e:
            err_msg = f"{e}\n{traceback.format_exc()}"
            log(f"[{__id__}] wizard_finalize error: {err_msg}")
            _show_bulletin_error(str(e))

    threading.Thread(target=_do, daemon=True).start()


def _finish_wizard_fragment(fragment=None):
    try:
        fragment = fragment or get_last_fragment()
        if fragment:
            fragment.finishFragment()
    except Exception as e:
        log(f"[{__id__}] close wizard fragment: {e}")


def _get_setting_string(key, default=""):
    try:
        return str(_ctrl().getPluginSettingString(__id__, key, default) or "").strip()
    except Exception:
        return default


def _reload_settings_after_wizard(ctrl):
    try:
        time.sleep(0.4)
        ctrl.loadPluginSettings(__id__)
    except Exception as e:
        log(f"[{__id__}] reload after wizard: {e}")


def _edit_subfragment_index(sc, sub_keys):
    if not sc or sc.get("type") != "open_settings":
        try:
            return _ctrl().getPluginSettingInt(__id__, "__wiz_subfragment", 0)
        except Exception:
            return 0
    value = sc.get("sub_fragment", "")
    try:
        return sub_keys.index(value) if value else 0
    except ValueError:
        return 0


def _edit_setting_index(sc, settings):
    if not sc or sc.get("type") != "operate_setting":
        try:
            return _ctrl().getPluginSettingInt(__id__, "__wiz_setting", 0)
        except Exception:
            return 0
    value = sc.get("setting_key", "")
    for index, setting in enumerate(settings):
        if setting.get("key") == value:
            return index
    return 0


def _icon_exists(icon_key):
    icon_key = str(icon_key or "").strip()
    if not icon_key:
        return False
    if icon_key in {key for key, _ in PRESET_ICONS}:
        return True
    if "/" in icon_key or " " in icon_key:
        return False
    try:
        context = ApplicationLoader.applicationContext
        resources = context.getResources()
        package_name = context.getPackageName()
        return int(resources.getIdentifier(icon_key, "drawable", package_name)) != 0
    except Exception as e:
        log(f"[{__id__}] icon lookup failed for {icon_key}: {e}")
        return False


def _selected_icon_key():
    custom = _get_setting_string(f"__wiz_custom_icon_{WIZ_SESSION}")
    if custom:
        return custom
    return _get_setting_string(f"__wiz_icon_{WIZ_SESSION}", "media_settings")


def _icon_title(icon_key):
    for key, title_key in PRESET_ICONS:
        if key == icon_key:
            return _s(title_key)
    return icon_key or _s(PRESET_ICONS[0][1])


def _save_selected_icon(plugin, icon_key):
    icon_key = str(icon_key or "").strip()
    if not _icon_exists(icon_key):
        _show_bulletin_error(_s("icon_not_found"))
        return
    try:
        ctrl = _ctrl()
        plugin.set_setting(f"__wiz_icon_{WIZ_SESSION}", icon_key)
        plugin.set_setting(f"__wiz_custom_icon_{WIZ_SESSION}", "")
        ctrl.loadPluginSettings(__id__)
        _show_bulletin_success(f"{_s('icon_selected')}: {_icon_title(icon_key)}")
    except Exception as e:
        log(f"[{__id__}] select icon error: {e}")


def _remember_custom_icon(value):
    return None


def build_icon_picker(plugin):
    items = []
    for icon_key, title_key in PRESET_ICONS:
        items.append(
            Text(
                text=_s(title_key),
                icon=icon_key,
                on_click=lambda _value, key=icon_key: _save_selected_icon(plugin, key),
            )
        )
    items.append(Divider())
    custom_key = _get_setting_string(f"__wiz_custom_icon_{WIZ_SESSION}")
    items.append(
        Input(
            key=f"__wiz_custom_icon_{WIZ_SESSION}",
            text=_s("custom_icon_name"),
            subtext=_s("custom_icon_name_sub"),
            default=custom_key,
            on_change=_remember_custom_icon,
        )
    )
    if custom_key:
        status_key = "icon_found" if _icon_exists(custom_key) else "icon_not_found"
        items.append(Text(text=_s(status_key), red=status_key == "icon_not_found"))
    return items
