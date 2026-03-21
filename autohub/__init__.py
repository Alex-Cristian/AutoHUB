import importlib
import sys


# Compatibility aliases for Django's test discovery when the repository root
# shares the same name as the Django project package.
for _module in ('accounts', 'bookings', 'core', 'invoices', 'services'):
    try:
        sys.modules.setdefault(f'{__name__}.{_module}', importlib.import_module(_module))
    except ModuleNotFoundError:
        continue

sys.modules.setdefault(f'{__name__}.autohub', sys.modules[__name__])
