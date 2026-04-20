from fastapi import HTTPException, status


class UnauthorizedException(HTTPException):
    def __init__(self, detail: str = "Non authentifié"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class ForbiddenException(HTTPException):
    def __init__(self, detail: str = "Accès refusé"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class NotFoundException(HTTPException):
    def __init__(self, detail: str = "Ressource introuvable"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ChallengeExpiredException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_410_GONE,
            detail="Ce lien ou code a expiré",
        )


class ChallengeAlreadyUsedException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_410_GONE,
            detail="Ce lien ou code a déjà été utilisé",
        )


class SessionExpiredException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée",
            headers={"X-Redirect": "/session-expired"},
        )


class UpstreamUnavailableException(HTTPException):
    def __init__(self, detail: str = "Environnement indisponible"):
        super().__init__(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
