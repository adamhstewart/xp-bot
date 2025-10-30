"""
Custom exceptions for XP Bot
"""


class XPBotError(Exception):
    """Base exception for all XP Bot errors"""
    pass


class DatabaseError(XPBotError):
    """Base exception for database-related errors"""
    pass


class DatabaseConnectionError(DatabaseError):
    """Database connection failed"""
    pass


class DatabaseTimeoutError(DatabaseError):
    """Database operation timed out"""
    pass


class CharacterError(XPBotError):
    """Base exception for character-related errors"""
    pass


class CharacterNotFoundError(CharacterError):
    """Character does not exist"""
    def __init__(self, char_name: str, user_id: int = None):
        self.char_name = char_name
        self.user_id = user_id
        if user_id:
            super().__init__(f"Character '{char_name}' not found for user {user_id}")
        else:
            super().__init__(f"Character '{char_name}' not found")


class DuplicateCharacterError(CharacterError):
    """Character with this name already exists"""
    def __init__(self, char_name: str, user_id: int):
        self.char_name = char_name
        self.user_id = user_id
        super().__init__(f"Character '{char_name}' already exists for user {user_id}")


class ValidationError(XPBotError):
    """Input validation failed"""
    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"{field}: {message}")
