from client_utils import get_last_fragment
from com.exteragram.messenger.plugins import PluginsController
from java import dynamic_proxy, jclass

from header import __id__
from i18n.locales import _s


def _ctrl():
    return PluginsController.getInstance()


def _plugin_name(pid):
    if pid == __id__:
        return _s("shortcuts")
    try:
        p = _ctrl().plugins.get(pid)
        if p and p.getName():
            return str(p.getName())
    except Exception:
        pass
    return pid


def _plugin_exists(pid):
    try:
        return _ctrl().plugins.get(pid) is not None
    except Exception:
        return False


def _to_py_list(seq):
    if seq is None:
        return []
    try:
        return list(seq)
    except Exception:
        pass
    try:
        arr = seq.toArray()
        return list(arr)
    except Exception:
        pass
    try:
        n = int(seq.size())
        return [seq.get(i) for i in range(n)]
    except Exception:
        pass
    return []


def _remove_menu_item_safe(plugin, menu_id):
    if not menu_id:
        return
    try:
        plugin.remove_menu_item(menu_id)
    except Exception:
        pass


def _open_link_key(prefix, key, alias=None):
    tail = alias or key
    if not tail:
        return None
    return f"{prefix}:{tail}" if prefix else tail


def _shortcut_norm_text(value):
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def _setting_value_key(data):
    explicit = data.get("setting_value_key", data.get("value_key", None))
    key = explicit if explicit is not None else data.get("setting_key", data.get("key", ""))
    if key:
        if explicit is None and ":" in str(key):
            return str(key).split(":")[-1]
        return str(key)
    return ""


def _invoke_sub_fragment_callback(cb):
    if cb is None:
        return None
    if callable(cb):
        try:
            return cb()
        except Exception:
            try:
                return cb(None)
            except Exception:
                pass
    for method in ("call", "get", "run", "invoke", "create", "createSubFragment", "apply"):
        if hasattr(cb, method):
            try:
                fn = getattr(cb, method)
                try:
                    return fn()
                except Exception:
                    return fn(None)
            except Exception:
                pass
    return None


def _run_on_plugins_queue(fn):
    try:
        Runnable = dynamic_proxy(jclass("java.lang.Runnable"))

        class Task(Runnable):
            def run(self):
                fn()

        PluginsController.runOnPluginsQueue(Task())
    except Exception:
        fn()


def _dialog_context():
    frag = get_last_fragment()
    if not frag:
        return None, None
    try:
        return frag, frag.getParentActivity()
    except Exception:
        return frag, None


def _show_dialog_safe(frag, dialog):
    try:
        frag.showDialog(dialog)
    except Exception:
        dialog.show()


def _show_bulletin_success(text, subtext=None, fragment=None):
    def _do():
        try:
            from ui.bulletin import BulletinHelper

            frag = fragment or get_last_fragment()
            if frag:
                try:
                    BulletinHelper.show_success(text=text, subtext=subtext, fragment=frag)
                    return
                except TypeError:
                    try:
                        BulletinHelper.show_success(text=text, fragment=frag)
                        return
                    except TypeError:
                        pass
            BulletinHelper.show_success(text)
        except Exception as e:
            from client_utils import log

            log(f"[{__id__}] show_bulletin_success: {e}")

    from client_utils import run_on_ui_thread

    run_on_ui_thread(_do)


def _show_bulletin_error(text, subtext=None, fragment=None):
    def _do():
        try:
            from ui.bulletin import BulletinHelper

            frag = fragment or get_last_fragment()
            if frag:
                try:
                    BulletinHelper.show_error(text=text, subtext=subtext, fragment=frag)
                    return
                except TypeError:
                    try:
                        BulletinHelper.show_error(text=text, fragment=frag)
                        return
                    except TypeError:
                        pass
            BulletinHelper.show_error(text)
        except Exception as e:
            from client_utils import log

            log(f"[{__id__}] show_bulletin_error: {e}")

    from client_utils import run_on_ui_thread

    run_on_ui_thread(_do)


def _show_bulletin_info(text, subtext=None, fragment=None):
    def _do():
        try:
            from ui.bulletin import BulletinHelper

            frag = fragment or get_last_fragment()
            if frag:
                try:
                    BulletinHelper.show_info(text=text, subtext=subtext, fragment=frag)
                    return
                except TypeError:
                    try:
                        BulletinHelper.show_info(text=text, fragment=frag)
                        return
                    except TypeError:
                        pass
            BulletinHelper.show_info(text)
        except Exception as e:
            from client_utils import log

            log(f"[{__id__}] show_bulletin_info: {e}")

    from client_utils import run_on_ui_thread

    run_on_ui_thread(_do)


def _finish_and_show_success(target_fragment, text):
    def _do():
        try:
            if target_fragment is not None:
                target_fragment.finishFragment()
            else:
                curr = get_last_fragment()
                if curr:
                    curr.finishFragment()
        except Exception:
            pass

        def _show():
            try:
                _show_bulletin_success(text)
            except Exception:
                pass

        try:
            from org.telegram.messenger import AndroidUtilities

            Runnable = dynamic_proxy(jclass("java.lang.Runnable"))

            class PostTask(Runnable):
                def run(self):
                    _show()

            AndroidUtilities.runOnUIThread(PostTask(), 150)
        except Exception:
            _show()

    from client_utils import run_on_ui_thread

    run_on_ui_thread(_do)


def _loc_label(loc):
    locations = _sc_locations({"location": loc} if isinstance(loc, str) else loc)
    labels = {
        "drawer": _s("drawer"),
        "chat": _s("chat_menu"),
        "message": _s("message_menu"),
        "profile": _s("profile_menu"),
    }
    return " + ".join(labels[location] for location in locations) if locations else _s("drawer")


def _sc_locations(sc):
    locations = sc.get("locations") if isinstance(sc, dict) else None
    if isinstance(locations, (list, tuple)):
        return [location for location in locations if location in {"drawer", "chat", "message", "profile"}]
    location = sc.get("location", "drawer") if isinstance(sc, dict) else sc
    if location == "both":
        return ["drawer", "chat"]
    if location in {"drawer", "chat", "message", "profile"}:
        return [location]
    return ["drawer"]


def _shortcut_title(sc):
    sk = sc.get("setting_key", "")
    return sk.split(":")[-1] if ":" in sk else sk


def _sc_label(sc):
    if sc.get("label"):
        return str(sc.get("label"))[:50]
    pid = sc.get("plugin_id", "?")
    pname = _plugin_name(pid)
    t = sc.get("type", "toggle_plugin")
    if t == "toggle_plugin":
        return f"Toggle: {pname}"[:50]
    elif t == "open_settings":
        return f"{_s('settings')}: {pname}"[:50]
    elif t == "operate_setting":
        return f"{pname}: {_shortcut_title(sc)}"[:50]
    return str(pname)[:50]


def _get_shortcut_state(sc):
    try:
        t = sc.get("type", "toggle_plugin")
        pid = sc.get("plugin_id", "")
        if t == "toggle_plugin":
            p = _ctrl().plugins.get(pid)
            if p:
                enabled = bool(p.isEnabled())
                return (enabled, _s("status_on") if enabled else _s("status_off"))
            return (False, _s("status_off"))
        elif t == "operate_setting":
            st = sc.get("setting_type", "switch")
            vk = _setting_value_key(sc)
            if st == "switch":
                val = bool(_ctrl().getPluginSettingBoolean(pid, vk, False))
                return (val, _s("status_on") if val else _s("status_off"))
            elif st == "selector":
                cur = _ctrl().getPluginSettingInt(pid, vk, 0)
                opts = sc.get("setting_items") or sc.get("items") or []
                if 0 <= int(cur) < len(opts):
                    return (None, str(opts[int(cur)]))
                return (None, str(cur))
            elif st == "input":
                val = str(_ctrl().getPluginSettingString(pid, vk, "") or "")
                return (None, val)
    except Exception:
        pass
    return (None, "")


def _sc_status_text(sc):
    _, text = _get_shortcut_state(sc)
    return text


def _sc_subtext(sc):
    loc_str = _loc_label(sc)
    if sc.get("is_system"):
        return loc_str
    t = sc.get("type", "toggle_plugin")
    type_descriptions = {
        "toggle_plugin": _s("toggle_plugin"),
        "open_settings": _s("open_settings"),
        "operate_setting": _s("operate_setting"),
    }
    type_desc = type_descriptions.get(t, "")
    parts = []
    if type_desc:
        parts.append(type_desc)
    if loc_str:
        parts.append(loc_str)
    return " • ".join(parts)


def _sc_menu_label(sc):
    base_label = str(sc.get("label") or _sc_label(sc))[:50]
    if sc.get("is_system"):
        return (base_label, None)
    _, state_text = _get_shortcut_state(sc)
    if state_text:
        return (f"{base_label}: {state_text}"[:60], state_text)
    return (base_label, None)
