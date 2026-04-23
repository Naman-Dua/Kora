from storage import init_db, load_all_settings, load_setting, save_setting

DEFAULT_SETTINGS = {
    "model_name": "llama3.1:8b",
    "enable_wake_word": False,
    "speak_text_replies": False,
    "require_action_confirmation": True,
    "window_always_on_top": True,
}


def load_settings():
    init_db()
    merged = dict(DEFAULT_SETTINGS)
    merged.update(load_all_settings())
    return merged


def get_setting(key, default=None):
    init_db()
    if default is None:
        default = DEFAULT_SETTINGS.get(key)
    return load_setting(key, default)


def save_settings(updates):
    init_db()
    cleaned = {}
    for key, value in dict(updates).items():
        if key not in DEFAULT_SETTINGS:
            continue
        save_setting(key, value)
        cleaned[key] = value
    return cleaned
