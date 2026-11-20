"""Authentication, password hashing, and JWT utilities (placeholder for SDD-2)."""


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using a strong adaptive hashing algorithm."""
    raise NotImplementedError("Password hashing will be implemented in SDD-2 / Step 4.")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    raise NotImplementedError("Password verification will be implemented in SDD-2 / Step 4.")


def create_access_token(subject: str) -> str:
    """Issue a signed JWT access token."""
    raise NotImplementedError("JWT issuance will be implemented in SDD-2 / Step 4.")

