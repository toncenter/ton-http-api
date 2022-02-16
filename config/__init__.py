import os
import yaml
import importlib.resources


class SettingsDict(dict):
    """dot.notation access to dictionary attributes"""
    def __getattr__(self, *args):         
        val = dict.get(self, *args)         
        return SettingsDict(val) if type(val) is dict else val      
    __setattr__ = None
    __delattr__ = None


with importlib.resources.open_text(__package__, "settings.yaml") as f:
    settings = SettingsDict(yaml.safe_load(os.path.expandvars(f.read())))
