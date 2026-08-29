from java.util import Locale

STRINGS = {
    "en": {
        # 1. Main Settings List
        "shortcuts": "Shortcuts",
        "settings": "Settings",
        "add_shortcut": "Add shortcut",
        "plugins": "Plugins",
        "no_plugins": "No other plugins found",
        # 2. Shortcut Actions Page
        "open_shortcut": "Open",
        "edit_shortcut": "Edit",
        "copy_deeplink": "Share shortcut",
        "remove_shortcut": "Delete",
        "move_up": "Move up",
        "move_down": "Move down",
        "shortcut_reordered": "Order updated",
        "shortcut_not_found": "Shortcut not found",
        "cannot_remove_system": "System shortcut cannot be deleted",
        # 3. Wizard: Locations n' Action Type
        "location": "Location",
        "location_hint": "Where to place the shortcut",
        "location_required": "Pick at least one location",
        "drawer": "Side menu",
        "chat_menu": "Chat menu",
        "message_menu": "Message menu",
        "profile_menu": "Profile menu",
        "type": "Action type",
        "toggle_plugin": "Toggle on/off",
        "open_settings": "Open settings page",
        "operate_setting": "Interact with setting",
        "toggle_only_warning": "This plugin only supports toggling on/off",
        "sub_fragment": "Sub-page",
        "root_settings": "Main settings",
        "select_setting": "Pick a setting to control",
        "no_settings": "No settings found",
        # 4. Wizard: Customization n' Saving
        "custom_label": "Name",
        "custom_icon": "Icon",
        "create": "Create",
        "save": "Save",
        "cancel": "Cancel",
        "shortcut_created": "Shortcut created",
        "shortcut_updated": "Shortcut updated",
        "shortcut_removed": "Shortcut deleted",
        # 5. Icon Picker n' Custom Drawables
        "custom_icon_name": "Custom icon",
        "custom_icon_name_sub": "Enter drawable name from the app",
        "icon_found": "Icon found",
        "icon_not_found": "Icon not found",
        "icon_selected": "Icon selected",
        "icon_media_settings": "Settings",
        "icon_msg_settings": "Gear",
        "icon_msg_folders": "Folders",
        "icon_menu_privacy": "Privacy",
        "icon_msg_notifications": "Notifications",
        "icon_msg_secret": "Lock",
        "icon_msg_theme": "Theme",
        "icon_msg_language": "Language",
        "icon_media_share": "Share",
        "icon_msg_stats": "Stats",
        "icon_msg_info": "Info",
        "icon_msg_work": "Work",
        "icon_msg_channel": "Channel",
        "icon_msg_bot": "Bot",
        "icon_msg_openprofile": "Profile",
        "icon_msg_palette": "Palette",
        "icon_msg_customize": "Customize",
        "icon_msg_media": "Data & storage",
        "icon_msg_autodelete": "Auto-delete",
        # 6. Dialogs n' Selectors
        "choose_value": "Pick value",
        "text_value": "Value",
        # 7. Status
        "status": "Status",
        "status_on": "ON",
        "status_off": "OFF",
        "action": "Action",
        "plugin_not_found": "Plugin not found",
        "setting_not_found": "Setting not found...",
        "plugin_disabled_open_manager": "Enable it... Please...",
        "error": "Error",
        # 8. Deeplinks
        "deeplink_copied": "Link copied",
        "add_deeplink_confirm": "Add this shortcut?",
        "shortcut_exists": "This shortcut already exists. Update it?",
        "plugin_not_installed": "Plugin is not installed yet",
        "run_now": "Run",
        "update": "Update",
        "invalid_deeplink": "Invalid shortcut link",
    },
    "ru": {
        # 1. Главный экран плагина
        "shortcuts": "Ярлыки",
        "settings": "Настройки",
        "add_shortcut": "Добавить ярлык",
        "plugins": "Плагины",
        "no_plugins": "Других плагинов пока нет",
        # 2. Экран управления ярлыком
        "open_shortcut": "Открыть",
        "edit_shortcut": "Изменить",
        "copy_deeplink": "Поделиться ярлыком",
        "remove_shortcut": "Удалить",
        "move_up": "Переместить выше",
        "move_down": "Переместить ниже",
        "shortcut_reordered": "Порядок изменён",
        "shortcut_not_found": "Ярлык не найден",
        "cannot_remove_system": "Системный ярлык нельзя удалить",
        # 3. Мастер: локации и тип действия
        "location": "Где показывать",
        "location_hint": "Где появится кнопка ярлыка",
        "location_required": "Выбери хотя бы одно место",
        "drawer": "Боковое меню",
        "chat_menu": "Меню чата",
        "message_menu": "Меню сообщения",
        "profile_menu": "Меню профиля",
        "type": "Что делать",
        "toggle_plugin": "Включить/выключить плагин",
        "open_settings": "Открыть экран настроек",
        "operate_setting": "Взаимодействовать с настройкой",
        "toggle_only_warning": "Этот плагин можно только включить/выключить",
        "sub_fragment": "Подстраница",
        "root_settings": "Главная страница",
        "select_setting": "Выбери нужную настройку",
        "no_settings": "Настроек нет",
        # 4. Мастер: кастомизация и сохранение
        "custom_label": "Название",
        "custom_icon": "Иконка",
        "create": "Создать",
        "save": "Сохранить",
        "cancel": "Отмена",
        "shortcut_created": "Ярлык создан",
        "shortcut_updated": "Ярлык обновлён",
        "shortcut_removed": "Ярлык удалён",
        # 5. Выбор иконки и кастомный drawable
        "custom_icon_name": "Своя иконка",
        "custom_icon_name_sub": "Введи имя drawable-ресурса",
        "icon_found": "Иконка найдена",
        "icon_not_found": "Иконка не найдена",
        "icon_selected": "Иконка выбрана",
        "icon_media_settings": "Настройки",
        "icon_msg_settings": "Шестерёнка",
        "icon_msg_folders": "Папки",
        "icon_menu_privacy": "Приватность",
        "icon_msg_notifications": "Уведомления",
        "icon_msg_secret": "Замок",
        "icon_msg_theme": "Тема",
        "icon_msg_language": "Язык",
        "icon_media_share": "Поделиться",
        "icon_msg_stats": "Статистика",
        "icon_msg_info": "Инфо",
        "icon_msg_work": "Работа",
        "icon_msg_channel": "Канал",
        "icon_msg_bot": "Бот",
        "icon_msg_openprofile": "Профиль",
        "icon_msg_palette": "Палитра",
        "icon_msg_customize": "Кастомизация",
        "icon_msg_media": "Данные и память",
        "icon_msg_autodelete": "Автоудаление",
        # 6. Диалоги ввода и селекторы
        "choose_value": "Выбери значение",
        "text_value": "Значение",
        # 7. Статусы
        "status": "Статус",
        "status_on": "ВКЛ",
        "status_off": "ВЫКЛ",
        "action": "Действие",
        "plugin_not_found": "Плагин не найден",
        "setting_not_found": "Такой настройки нет...",
        "plugin_disabled_open_manager": "Включи его... Пожалуйста...",
        "error": "Ошибка",
        # 8. Диплинки
        "deeplink_copied": "Ссылка скопирована",
        "add_deeplink_confirm": "Добавить этот ярлык?",
        "shortcut_exists": "Такой ярлык уже есть. Обновить?",
        "plugin_not_installed": "Плагин ещё не установлен",
        "run_now": "Запустить",
        "update": "Обновить",
        "invalid_deeplink": "Неправильная ссылка на ярлык",
    },
}


def _is_ru():
    try:
        from org.telegram.messenger import LocaleController

        curr = LocaleController.getInstance().getCurrentLocale()
        if curr and curr.getLanguage():
            return curr.getLanguage().lower().startswith("ru")
    except Exception:
        pass
    try:
        return Locale.getDefault().getLanguage().lower().startswith("ru")
    except Exception:
        return True


def _s(key):
    lang = "ru" if _is_ru() else "en"
    return STRINGS.get(lang, STRINGS["en"]).get(key, key)
