import threading
import traceback

from android_utils import run_on_ui_thread
from client_utils import log
from ui.bulletin import BulletinHelper

from data.constants import PRESET_ICONS
from header import __id__
from i18n.locales import _s
from ui.settings import Divider, Header, Input, Selector, Text
from utils.helpers import _ctrl, _plugin_name, _sc_label, _setting_value_key
from utils.scanner import _collect_settings, _collect_sub_fragments, _has_settings_reliably, _plugin_ids


def build_wizard_step1(plugin):
    items = []
    items.append(Header(text=_s("location")))
    items.append(Selector(key="__wiz_loc", text=_s("location"), items=[_s("drawer"), _s("chat_menu"), _s("both_places")], default=0))
    items.append(Header(text=_s("type")))
    items.append(Selector(key="__wiz_type", text=_s("type"), items=[_s("toggle_plugin"), _s("open_settings"), _s("operate_setting")], default=0))
    items.append(Text(text=_s("next"), accent=True, create_sub_fragment=lambda: build_wizard_step2(plugin)))
    return items


def build_wizard_step2(plugin):
    def _build():
        try:
            type_i = _ctrl().getPluginSettingInt(__id__, "__wiz_type", 0)
        except Exception:
            type_i = 0

        pids = []
        if type_i == 0:  # toggle_plugin
            pids = _plugin_ids()
        elif type_i == 1:  # open_settings / sub-page
            pids = [pid for pid in _plugin_ids() if _has_settings_reliably(pid)]
        else:  # operate_setting
            pids = [pid for pid in _plugin_ids() if _has_settings_reliably(pid)]

        if not pids:
            return [Divider(text=_s("no_plugins"))]

        pnames = [_plugin_name(p) for p in pids]

        try:
            plug_i = _ctrl().getPluginSettingInt(__id__, "__wiz_plugin", 0)
        except Exception:
            plug_i = 0
        if plug_i < 0 or plug_i >= len(pids):
            plug_i = 0
        selected_pid = pids[plug_i]

        items = []

        def _on_plugin_changed(idx):
            try:
                _ctrl().setPluginSetting(__id__, "__wiz_subfragment", 0)
                _ctrl().loadPluginSettings(__id__)
            except Exception as e:
                log(f"[{__id__}] _on_plugin_changed: {e}")

        items.append(Header(text=_s("plugins")))
        items.append(Selector(key="__wiz_plugin", text=_s("plugins"), items=pnames, default=plug_i, on_change=_on_plugin_changed))

        sub_keys = ["root"]
        if type_i == 1:  # open_settings
            subs = _collect_sub_fragments(selected_pid)
            if subs:
                sub_titles = [_s("root_settings")]
                for sub in subs:
                    sub_keys.append(sub["key"])
                    sub_titles.append(sub["text"])

                items.append(Header(text=_s("sub_fragment")))
                items.append(Selector(key="__wiz_subfragment", text=_s("sub_fragment"), items=sub_titles, default=0))

            items.append(
                Text(text=_s("next"), accent=True, create_sub_fragment=lambda: build_wizard_step_customize(plugin, pids, "open_settings", sub_keys=sub_keys))
            )
        elif type_i == 2:  # operate_setting -> choose setting
            items.append(Text(text=_s("next"), accent=True, create_sub_fragment=lambda: build_wizard_step3_setting(plugin, pids)))
        else:  # toggle_plugin -> custom label & icon
            items.append(Text(text=_s("next"), accent=True, create_sub_fragment=lambda: build_wizard_step_customize(plugin, pids, "toggle_plugin")))

        return items

    return plugin._with_spinner(_build)


def build_wizard_step3_setting(plugin, pids):
    def _build():
        try:
            plug_i = _ctrl().getPluginSettingInt(__id__, "__wiz_plugin", 0)
        except Exception:
            plug_i = 0
        if plug_i < 0 or plug_i >= len(pids):
            plug_i = 0
        pid = pids[plug_i]

        settings = _collect_settings(pid)
        if not settings:
            return [Divider(text=_s("no_settings"))]

        names = [s.get("text", s.get("key", "")) for s in settings]
        items = []
        items.append(Header(text=_s("select_setting")))
        items.append(Selector(key="__wiz_setting", text=_s("select_setting"), items=names, default=0))
        items.append(
            Text(text=_s("next"), accent=True, create_sub_fragment=lambda: build_wizard_step_customize(plugin, pids, "operate_setting", settings=settings))
        )
        return items

    return plugin._with_spinner(_build)


def build_wizard_step_customize(plugin, pids, stype, sub_keys=None, settings=None):
    items = []
    items.append(Header(text=_s("custom_label")))

    try:
        plug_i = _ctrl().getPluginSettingInt(__id__, "__wiz_plugin", 0)
    except Exception:
        plug_i = 0
    if plug_i < 0 or plug_i >= len(pids):
        plug_i = 0
    pid = pids[plug_i]
    def_label = _plugin_name(pid)

    items.append(Input(key="__wiz_label", text=_s("custom_label"), default=def_label))

    items.append(Header(text=_s("custom_icon")))
    icon_names = [pair[1] for pair in PRESET_ICONS]
    items.append(Selector(key="__wiz_icon", text=_s("custom_icon"), items=icon_names, default=0))

    items.append(Text(text=_s("create"), accent=True, on_click=lambda v: wizard_finalize(plugin, pids, stype, sub_keys=sub_keys, settings=settings)))
    return items


def wizard_finalize(plugin, pids, stype, sub_keys=None, settings=None):
    def _do():
        try:
            ctrl = _ctrl()
            loc_i = ctrl.getPluginSettingInt(__id__, "__wiz_loc", 0)
            plug_i = ctrl.getPluginSettingInt(__id__, "__wiz_plugin", 0)
            icon_i = ctrl.getPluginSettingInt(__id__, "__wiz_icon", 0)
            custom_label = ctrl.getPluginSettingString(__id__, "__wiz_label", "").strip()

            loc = "both" if loc_i == 2 else ("drawer" if loc_i == 0 else "chat")
            if plug_i < 0 or plug_i >= len(pids):
                plug_i = 0
            pid = pids[plug_i]

            if icon_i < 0 or icon_i >= len(PRESET_ICONS):
                icon_i = 0
            icon_key = PRESET_ICONS[icon_i][0]

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
