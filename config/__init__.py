import yaml
import importlib.resources

from typing import Dict, Any


class SettingsDict(dict):
    """dot.notation access to dictionary attributes"""
    def __getattr__(self, *args):         
        val = dict.get(self, *args)         
        return SettingsDict(val) if type(val) is dict else val      
    __setattr__ = None
    __delattr__ = None


with importlib.resources.open_text(__package__, "settings.yaml") as f:
    settings = yaml.safe_load(f)

    # reading passwords once
    def read_password(data: Dict[str, Any]):
        password_file = data.pop('password_file')
        if password_file:
            with open(password_file, 'r') as f:
                data['password'] = f.read()
        return data
    for k, v in settings.items():
        read_password(v)

    # to SettingsDict
    settings = SettingsDict(settings)
