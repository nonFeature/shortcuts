import threading
import time
import traceback

from android_utils import run_on_ui_thread
from client_utils import get_last_fragment, log
from org.telegram.messenger import ApplicationLoader
from ui.bulletin import BulletinHelper

from data.constants import PRESET_ICONS
from header import __id__
from i18n.locales import _s
from ui.settings import Divider, Header, Input, Selector, Switch, Text
from utils.helpers import _ctrl, _plugin_name, _sc_label, _sc_locations, _setting_value_key
from utils.scanner import _collect_settings, _collect_sub_fragments, _has_settings_reliably, _plugin_ids

LOCATION_KEYS = ("drawer", "chat", "message", "profile")


def _init_new_wizard_state(plugin, pids):
    selected_pid = pids[0] if pids else ""
    for location_key in LOCATION_KEYS:
        plugin.set_setting(f"__wiz_loc_{location_key}", location_key == "drawer")
    plugin.set_setting("__wiz_plugin", 0)
    plugin.set_setting("__wiz_type", 0)
    plugin.set_setting("__wiz_subfragment", 0)
    plugin.set_setting("__wiz_setting", 0)
    plugin.set_setting("__wiz_label", _plugin_name(selected_pid) if selected_pid else "")
    plugin.set_setting("__wiz_icon", "media_settings")
    plugin.set_setting("__wiz_custom_icon", "")


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
        plugin.set_setting(f"__wiz_loc_{location_key}", location_key in locations)
    plugin.set_setting("__wiz_plugin", plugin_index)
    plugin.set_setting("__wiz_type", type_index)
    plugin.set_setting("__wiz_label", str(sc.get("label", "") or ""))
    plugin.set_setting("__wiz_icon", str(sc.get("icon", "media_settings") or "media_settings"))
    plugin.set_setting("__wiz_custom_icon", "")


def build_new_wizard(plugin):
    initialized = False

    def _render():
        nonlocal initialized
        pids = _plugin_ids()
        if not initialized:
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
                key=f"__wiz_loc_{key}",
                text=_s(label_key),
                default=ctrl.getPluginSettingBoolean(__id__, f"__wiz_loc_{key}", False),
            )
            for key, label_key in (
                ("drawer", "drawer"),
                ("chat", "chat_menu"),
                ("message", "message_menu"),
                ("profile", "profile_menu"),
            )
        ]
        items.append(Divider(text=_s("location_hint")))
        if not pids:
            return [*items, Divider(text=_s("no_plugins"))]

        try:
            plug_i = ctrl.getPluginSettingInt(__id__, "__wiz_plugin", 0)
        except Exception:
            plug_i = 0
        if plug_i < 0 or plug_i >= len(pids):
            plug_i = 0
        selected_pid = pids[plug_i]

        items.append(
            Selector(
                key="__wiz_plugin",
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
            type_i = ctrl.getPluginSettingInt(__id__, "__wiz_type", 0)
        except Exception:
            type_i = 0
        if type_i < 0 or type_i > 2:
            type_i = 0

        items.append(
            Selector(
                key="__wiz_type",
                text=_s("type"),
                items=[_s("toggle_plugin"), _s("open_settings"), _s("operate_setting")],
                default=type_i,
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
                sub_default = _edit_subfragment_index(editing_sc, sub_keys)
                items.append(Selector(key="__wiz_subfragment", text=_s("sub_fragment"), items=sub_titles, default=sub_default))
            items.append(Divider())
            items.extend(build_wizard_step_customize(plugin, pids, "open_settings", sub_keys=sub_keys, edit_index=edit_index))
        elif type_i == 2:
            settings = _collect_settings(selected_pid, ensure_loaded=False)
            if not settings:
                return [Divider(text=_s("no_settings"))]
            names = [s.get("text", s.get("key", "")) for s in settings]
            setting_default = _edit_setting_index(editing_sc, settings)
            items.append(Selector(key="__wiz_setting", text=_s("select_setting"), items=names, default=setting_default))
            items.append(Divider())
            items.extend(build_wizard_step_customize(plugin, pids, "operate_setting", settings=settings, edit_index=edit_index))
        else:
            items.append(Divider())
            items.extend(build_wizard_step_customize(plugin, pids, "toggle_plugin", edit_index=edit_index))

        return items

    try:
        return _build()
    except Exception as e:
        log(f"[{__id__}] build_wizard_step1 error: {e}\n{traceback.format_exc()}")
        return [Header(text=_s("add_shortcut")), Divider(text=f"{_s('error')}: {e}")]


def _on_plugin_change(plugin, value, pids):
    try:
        index = int(value)
        if 0 <= index < len(pids):
            pid = pids[index]
            plugin.set_setting("__wiz_label", _plugin_name(pid))
            _ctrl().loadPluginSettings(pid)
    except Exception as e:
        log(f"[{__id__}] plugin selection error: {e}")


def build_wizard_step_customize(plugin, pids, stype, sub_keys=None, settings=None, edit_index=None):
    items = []
    try:
        plug_i = _ctrl().getPluginSettingInt(__id__, "__wiz_plugin", 0)
    except Exception:
        plug_i = 0
    if plug_i < 0 or plug_i >= len(pids):
        plug_i = 0
    pid = pids[plug_i]
    saved_label = _get_setting_string("__wiz_label")
    def_label = saved_label if saved_label else _plugin_name(pid)

    items.append(Input(key="__wiz_label", text=_s("custom_label"), default=def_label))

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
            locations = [key for key in LOCATION_KEYS if ctrl.getPluginSettingBoolean(__id__, f"__wiz_loc_{key}", False)]
            if not locations:
                run_on_ui_thread(lambda: BulletinHelper.show_error(_s("location_required")))
                return
            plug_i = ctrl.getPluginSettingInt(__id__, "__wiz_plugin", 0)
            custom_label = str(ctrl.getPluginSettingString(__id__, "__wiz_label", "") or "").strip()

            legacy_location = "both" if locations == ["drawer", "chat"] else locations[0]
            if plug_i < 0 or plug_i >= len(pids):
                plug_i = 0
            pid = pids[plug_i]

            icon_key = _selected_icon_key()
            if not _icon_exists(icon_key):
                run_on_ui_thread(lambda: BulletinHelper.show_error(_s("icon_not_found")))
                return

            sc_list = plugin._load_shortcuts()
            if edit_index is not None and 0 <= edit_index < len(sc_list):
                sc = dict(sc_list[edit_index])
                for key in ("sub_fragment", "setting_key", "setting_value_key", "setting_open_key", "setting_type", "setting_items"):
                    sc.pop(key, None)
                sc.update({"type": stype, "plugin_id": pid, "location": legacy_location, "locations": locations, "label": custom_label, "icon": icon_key})
            else:
                sc = {"type": stype, "plugin_id": pid, "location": legacy_location, "locations": locations, "label": custom_label, "icon": icon_key}

            if stype == "open_settings" and sub_keys:
                sub_i = ctrl.getPluginSettingInt(__id__, "__wiz_subfragment", 0)
                if 0 <= sub_i < len(sub_keys):
                    sub = sub_keys[sub_i]
                    if sub != "root":
                        sc["sub_fragment"] = sub

            elif stype == "operate_setting" and settings:
                set_i = ctrl.getPluginSettingInt(__id__, "__wiz_setting", 0)
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
            run_on_ui_thread(lambda: BulletinHelper.show_success(f"{_s(message_key)}: {label}"))
            run_on_ui_thread(lambda: _finish_wizard_fragment(wizard_fragment))
            threading.Thread(target=lambda: _reload_settings_after_wizard(ctrl), daemon=True).start()
        except Exception as e:
            log(f"[{__id__}] wizard_finalize error: {e}\n{traceback.format_exc()}")
            err_msg = str(e)
            run_on_ui_thread(lambda: BulletinHelper.show_error(err_msg))

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
        time.sleep(0.1)
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
    custom_key = _get_setting_string("__wiz_custom_icon")
    if custom_key:
        return custom_key

    saved_key = _get_setting_string("__wiz_icon")
    if saved_key in {key for key, _ in PRESET_ICONS}:
        return saved_key
    try:
        old_index = int(saved_key) if saved_key else _ctrl().getPluginSettingInt(__id__, "__wiz_icon", 0)
        if 0 <= old_index < len(PRESET_ICONS):
            return PRESET_ICONS[old_index][0]
    except Exception:
        pass
    return PRESET_ICONS[0][0]


def _icon_title(icon_key):
    for key, title_key in PRESET_ICONS:
        if key == icon_key:
            return _s(title_key)
    return icon_key or _s(PRESET_ICONS[0][1])


def _save_selected_icon(plugin, icon_key):
    icon_key = str(icon_key or "").strip()
    if not _icon_exists(icon_key):
        run_on_ui_thread(lambda: BulletinHelper.show_error(_s("icon_not_found")))
        return
    try:
        ctrl = _ctrl()
        plugin.set_setting("__wiz_icon", icon_key)
        plugin.set_setting("__wiz_custom_icon", "")
        ctrl.loadPluginSettings(__id__)
        run_on_ui_thread(lambda: BulletinHelper.show_success(f"{_s('icon_selected')}: {_icon_title(icon_key)}"))
    except Exception as e:
        log(f"[{__id__}] select icon error: {e}")


def _remember_custom_icon(value):
    return None


def build_icon_picker(plugin):
    items = [Header(text=_s("choose_icon"))]
    for icon_key, title_key in PRESET_ICONS:
        items.append(
            Text(
                text=_s(title_key),
                icon=icon_key,
                on_click=lambda _value, key=icon_key: _save_selected_icon(plugin, key),
            )
        )
    items.append(Divider())
    custom_key = _get_setting_string("__wiz_custom_icon")
    items.append(
        Input(
            key="__wiz_custom_icon",
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
