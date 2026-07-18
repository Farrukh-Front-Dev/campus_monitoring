import time
import logging
import requests
from typing import Optional, Dict, Any

class School21APIError(Exception):
    """School21 API error exception"""
    pass

class School21API:
    """School21 API client with automatic token refresh"""
    
    AUTH_URL = "https://auth.21-school.ru/auth/realms/EduPowerKeycloak/protocol/openid-connect/token"
    BASE_URL = "https://platform.21-school.ru/services/21-school/api/v1"
    TOKEN_LIFETIME = 300  # 5 minutes
    
    def __init__(self, username: str, password: str, logger: Optional[logging.Logger] = None):
        self.username = username
        self.password = password
        self.logger = logger or logging.getLogger("School21API")
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self.session = requests.Session()
        
    def authenticate(self) -> bool:
        """Authenticate and obtain access token"""
        data = {
            'client_id': 's21-open-api',
            'username': self.username,
            'password': self.password,
            'grant_type': 'password'
        }
        
        try:
            response = self.session.post(
                self.AUTH_URL,
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=15
            )
            response.raise_for_status()
            
            tokens = response.json()
            self._access_token = tokens.get('access_token')
            self._token_expires_at = time.time() + self.TOKEN_LIFETIME - 30
            
            self.logger.info("Authentication successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            return False
            
    def _ensure_authenticated(self) -> None:
        """Ensure valid access token exists"""
        if not self._access_token or time.time() >= self._token_expires_at:
            if not self.authenticate():
                raise School21APIError("Failed to authenticate")
                
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authorization"""
        return {
            'Authorization': f'Bearer {self._access_token}',
            'Content-Type': 'application/json'
        }
        
    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Make authenticated API request"""
        try:
            self._ensure_authenticated()
            response = self.session.get(
                f"{self.BASE_URL}/{endpoint}",
                headers=self._get_headers(),
                params=params,
                timeout=15
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None
            response.raise_for_status()
        except Exception as e:
            self.logger.error(f"API request failed ({endpoint}): {e}")
            return None
            
    def get_cluster_map(self, cluster_id: int, limit: int = 250) -> Optional[Dict[str, Any]]:
        """Get cluster map"""
        return self._make_request(f"clusters/{cluster_id}/map", params={'limit': limit})
        
    def get_participant_info(self, login: str) -> Optional[Dict[str, Any]]:
        """Get participant information"""
        return self._make_request(f"participants/{login}")
        
    def get_participant_logtime(self, login: str) -> Optional[Any]:
        """Get participant logtime"""
        return self._make_request(f"participants/{login}/logtime")
        
    def get_participant_points(self, login: str) -> Optional[Dict[str, Any]]:
        """Get participant points"""
        return self._make_request(f"participants/{login}/points")
        
    def get_participant_coalition(self, login: str) -> Optional[Dict[str, Any]]:
        """Get participant coalition"""
        return self._make_request(f"participants/{login}/coalition")

    def get_participant_projects(self, login: str) -> Optional[Any]:
        """Get participant projects"""
        return self._make_request(f"participants/{login}/projects")

    def get_participant_skills(self, login: str) -> Optional[Any]:
        """Get participant skills"""
        return self._make_request(f"participants/{login}/skills")

    def get_participant_achievements(self, login: str) -> Optional[Any]:
        """Get participant achievements"""
        return self._make_request(f"participants/{login}/achievements")

    def get_participant_feedbacks(self, login: str) -> Optional[Any]:
        """Get participant feedbacks"""
        return self._make_request(f"participants/{login}/feedbacks")

    def get_campuses(self) -> Optional[Any]:
        """Get campuses list"""
        return self._make_request("campuses")
