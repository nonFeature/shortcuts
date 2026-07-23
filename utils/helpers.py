from client_utils import get_last_fragment, log
from com.exteragram.messenger.plugins import PluginsController
from java import dynamic_proxy, jclass

def _ctrl():
    return PluginsController.getInstance()

def _plugin_name(pid):
    try:
        p = _ctrl().plugins.get(pid)
        if p and p.getName():
            return str(p.getName())
    except:
        pass
    return pid

def _plugin_exists(pid):
    try:
        return _ctrl().plugins.get(pid) is not None
    except:
        return False

def _to_py_list(seq):
    if seq is None:
        return []
    try:
        return list(seq)
    except:
        pass
    try:
        arr = seq.toArray()
        try:
            return list(arr)
        except:
            return [x for x in arr]
    except:
        pass
    try:
        n = int(seq.size())
        return [seq.get(i) for i in range(n)]
    except:
        pass
    return []

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
        except TypeError:
            pass
    if hasattr(cb, "call"):
        return cb.call()
    raise TypeError("unsupported sub-fragment callback")

def _run_on_plugins_queue(fn):
    try:
        Runnable = dynamic_proxy(jclass("java.lang.Runnable"))
        class Task(Runnable):
            def run(self):
                fn()
        PluginsController.runOnPluginsQueue(Task())
    except:
        fn()

def _dialog_context():
    frag = get_last_fragment()
    if not frag:
        return None, None
    try:
        return frag, frag.getParentActivity()
    except:
        return frag, None

def _show_dialog_safe(frag, dialog):
    try:
        frag.showDialog(dialog)
    except:
        dialog.show()

def _loc_label(loc):
    if loc == "chat":
        return _s("chat_menu")
    if loc == "both":
        return _s("both_places")
    return _s("drawer")

def _shortcut_title(sc):
    sk = sc.get("setting_key", "")
    return sk.split(":")[-1] if ":" in sk else sk

def _sc_label(sc):
    if sc.get("label"):
        return sc.get("label")
    pid = sc.get("plugin_id", "?")
    pname = _plugin_name(pid)
    t = sc.get("type", "toggle_plugin")
    if t == "toggle_plugin":
        return f"Toggle: {pname}"
    elif t == "open_settings":
        return f"{_s('settings')}: {pname}"
    elif t == "operate_setting":
        return f"{pname}: {_shortcut_title(sc)}"
    return pname
