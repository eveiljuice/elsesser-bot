from handlers.user import router as user_router
from handlers.admin import router as admin_router
from handlers.calculator import router as calculator_router

__all__ = ['user_router', 'admin_router', 'calculator_router']
