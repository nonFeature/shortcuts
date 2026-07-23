from base_plugin import BasePlugin, MenuItemData, MenuItemType
from ui.settings import Switch, Header, Divider, Text, Selector, Input
from ui.bulletin import BulletinHelper
from ui.alert import AlertDialogBuilder
from android_utils import run_on_ui_thread
from client_utils import get_last_fragment, log
from com.exteragram.messenger.plugins import PluginsController
from com.exteragram.messenger.plugins.ui import PluginSettingsActivity, PluginsActivity
from org.telegram.messenger import ApplicationLoader, AndroidUtilities
from java.util import Locale
from java import dynamic_proxy, jclass
import json
import time
import urllib.parse
import traceback

__name__ = "Shortcuts"
__description__ = "Создает ярлыки на настройки плагинов, их саб-фрагменты (подстраницы), переключатели и диплинки"
__version__ = "1.3"
__id__ = "shortcuts"
__author__ = "@feature_plugins"
__icon__ = "feature_plugins/3"
__min_version__ = "12.1.1"
