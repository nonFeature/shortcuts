import threading
import traceback

from android_utils import run_on_ui_thread
from client_utils import log
from org.telegram.messenger import ApplicationLoader
from ui.bulletin import BulletinHelper

from data.constants import PRESET_ICONS
from header import __id__
from i18n.locales import _s
from ui.settings import Divider, Header, Input, Selector, Text
from utils.helpers import _ctrl, _plugin_name, _sc_label, _setting_value_key
from utils.scanner import _collect_settings, _collect_sub_fragments, _has_settings_reliably, _plugin_ids


def build_wizard_step1(plugin):
    def _build():
        items = [
            Selector(key="__wiz_loc", text=_s("location"), items=[_s("drawer"), _s("chat_menu"), _s("both_places")], default=0),
            Divider(),
        ]
        pids = _plugin_ids()
        if not pids:
            return [*items, Divider(text=_s("no_plugins"))]

        try:
            plug_i = _ctrl().getPluginSettingInt(__id__, "__wiz_plugin", 0)
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
                on_change=lambda value: _ctrl().setPluginSetting(__id__, "__wiz_plugin", int(value)),
            )
        )
        items.append(Divider())

        if not _has_settings_reliably(selected_pid):
            try:
                current_type = _ctrl().getPluginSettingInt(__id__, "__wiz_type", 0)
            except Exception:
                current_type = 0
            if current_type != 0:
                _ctrl().setPluginSetting(__id__, "__wiz_type", 0)
            items.append(Divider(text=_s("toggle_only_warning")))
            items.append(Divider())
            items.extend(build_wizard_step_customize(plugin, pids, "toggle_plugin"))
            return items

        try:
            type_i = _ctrl().getPluginSettingInt(__id__, "__wiz_type", 0)
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
                on_change=lambda value: _ctrl().setPluginSetting(__id__, "__wiz_type", int(value)),
            )
        )

        if type_i == 1:
            sub_keys = ["root"]
            subs = _collect_sub_fragments(selected_pid)
            if subs:
                sub_titles = [_s("root_settings")]
                for sub in subs:
                    sub_keys.append(sub["key"])
                    sub_titles.append(sub["text"])
                items.append(Selector(key="__wiz_subfragment", text=_s("sub_fragment"), items=sub_titles, default=0))
            items.append(Divider())
            items.extend(build_wizard_step_customize(plugin, pids, "open_settings", sub_keys=sub_keys))
        elif type_i == 2:
            settings = _collect_settings(selected_pid)
            if not settings:
                return [Divider(text=_s("no_settings"))]
            names = [s.get("text", s.get("key", "")) for s in settings]
            items.append(Selector(key="__wiz_setting", text=_s("select_setting"), items=names, default=0))
            items.append(Divider())
            items.extend(build_wizard_step_customize(plugin, pids, "operate_setting", settings=settings))
        else:
            items.append(Divider())
            items.extend(build_wizard_step_customize(plugin, pids, "toggle_plugin"))

        return items

    return plugin._with_spinner(_build)


def build_wizard_step_customize(plugin, pids, stype, sub_keys=None, settings=None):
    items = []
    try:
        plug_i = _ctrl().getPluginSettingInt(__id__, "__wiz_plugin", 0)
    except Exception:
        plug_i = 0
    if plug_i < 0 or plug_i >= len(pids):
        plug_i = 0
    pid = pids[plug_i]
    def_label = _plugin_name(pid)

    items.append(Input(key="__wiz_label", text=_s("custom_label"), default=def_label))

    icon_key = _selected_icon_key()
    icon_title = _icon_title(icon_key)
    items.append(
        Text(
            text=_s("custom_icon"),
            subtext=icon_title,
            icon=icon_key,
            create_sub_fragment=lambda: build_icon_picker(plugin),
        )
    )

    items.append(Divider())
    items.append(Text(text=_s("create"), accent=True, on_click=lambda v: wizard_finalize(plugin, pids, stype, sub_keys=sub_keys, settings=settings)))
    return items


def wizard_finalize(plugin, pids, stype, sub_keys=None, settings=None):
    def _do():
        try:
            ctrl = _ctrl()
            loc_i = ctrl.getPluginSettingInt(__id__, "__wiz_loc", 0)
            plug_i = ctrl.getPluginSettingInt(__id__, "__wiz_plugin", 0)
            custom_label = ctrl.getPluginSettingString(__id__, "__wiz_label", "").strip()

            loc = "both" if loc_i == 2 else ("drawer" if loc_i == 0 else "chat")
            if plug_i < 0 or plug_i >= len(pids):
                plug_i = 0
            pid = pids[plug_i]

            icon_key = _selected_icon_key()
            if not _icon_exists(icon_key):
                run_on_ui_thread(lambda: BulletinHelper.show_info(_s("icon_not_found")))
                return

            sc = {"type": stype, "plugin_id": pid, "location": loc, "label": custom_label, "icon": icon_key}

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

            sc_list = plugin._load_shortcuts()
            sc_list.append(sc)
            plugin._save_shortcuts(sc_list)
            plugin._register_menu(sc)

            label = _sc_label(sc)
            run_on_ui_thread(lambda: BulletinHelper.show_info(f"{_s('shortcut_created')}: {label}"))
            ctrl.loadPluginSettings(__id__)
            plugin._open_self_settings()
        except Exception as e:
            log(f"[{__id__}] wizard_finalize error: {e}\n{traceback.format_exc()}")
            err_msg = str(e)
            run_on_ui_thread(lambda: BulletinHelper.show_info(err_msg))

    threading.Thread(target=_do, daemon=True).start()


def _get_setting_string(key, default=""):
    try:
        return str(_ctrl().getPluginSettingString(__id__, key, default) or "").strip()
    except Exception:
        return default


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
    for key, title in PRESET_ICONS:
        if key == icon_key:
            return title
    return icon_key or PRESET_ICONS[0][1]


def _save_selected_icon(plugin, icon_key):
    icon_key = str(icon_key or "").strip()
    if not _icon_exists(icon_key):
        run_on_ui_thread(lambda: BulletinHelper.show_info(_s("icon_not_found")))
        return
    try:
        ctrl = _ctrl()
        ctrl.setPluginSetting(__id__, "__wiz_icon", icon_key)
        ctrl.setPluginSetting(__id__, "__wiz_custom_icon", "")
        ctrl.loadPluginSettings(__id__)
    except Exception as e:
        log(f"[{__id__}] select icon error: {e}")


def _save_custom_icon(plugin):
    icon_key = _get_setting_string("__wiz_custom_icon")
    if not _icon_exists(icon_key):
        run_on_ui_thread(lambda: BulletinHelper.show_info(_s("icon_not_found")))
        return
    try:
        ctrl = _ctrl()
        ctrl.setPluginSetting(__id__, "__wiz_icon", icon_key)
        ctrl.loadPluginSettings(__id__)
        run_on_ui_thread(lambda: BulletinHelper.show_info(_s("icon_found")))
    except Exception as e:
        log(f"[{__id__}] custom icon save error: {e}")


def build_icon_picker(plugin):
    items = [Header(text=_s("choose_icon"))]
    for icon_key, icon_title in PRESET_ICONS:
        items.append(
            Text(
                text=icon_title,
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
        )
    )
    if custom_key:
        status_key = "icon_found" if _icon_exists(custom_key) else "icon_not_found"
        items.append(Text(text=_s(status_key), red=status_key == "icon_not_found"))
    items.append(Text(text=_s("check_icon"), accent=True, on_click=lambda _value: _save_custom_icon(plugin)))
    return items
