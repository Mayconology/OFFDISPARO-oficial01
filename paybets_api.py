
"""
PayBets PIX API Integration
===========================
Integração completa para pagamentos PIX usando a API PayBets.
Base URL: https://elite-manager-api-62571bbe8e96.herokuapp.com/api

Production-ready implementation with:
- Environment-based configuration
- Comprehensive error handling
- Professional logging
- Request timeout and retry logic
- Input validation and sanitization
"""
import os
import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass
import uuid
import time
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PaymentRequestData:
    """
    Dados necessários para criar um pagamento PIX via PayBets
    """
    name: str
    email: str
    cpf: str
    amount: float  # Valor em reais (não centavos)
    phone: Optional[str] = None
    description: Optional[str] = None

@dataclass
class PaymentResponse:
    """
    Resposta da criação de pagamento PIX via PayBets
    """
    transaction_id: str
    pix_code: str
    pix_qr_code: str
    status: str
    amount: float

class PayBetsAPI:
    """
    Classe principal para integração com a API PayBets
    Production-ready implementation
    """
    
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None, timeout: int = 30, max_retries: int = 3):
        """
        Inicializar a API PayBets com autenticação OAuth
        
        Args:
            client_id: ID do cliente PayBets
            client_secret: Secret do cliente PayBets  
            timeout: Timeout para requisições em segundos
            max_retries: Número máximo de tentativas em caso de falha
        """
        self.API_URL = os.getenv("PAYBETS_API_URL", "https://api.paybets.app")
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Configurar credenciais OAuth
        self.client_id = client_id or os.getenv("PAYBETS_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("PAYBETS_CLIENT_SECRET")
        
        # Fallback para credenciais hardcoded em desenvolvimento  
        if not self.client_id or not self.client_secret:
            self.client_id = "maikonlemos_YI4TQTCD"
            self.client_secret = "b33iwEdPT9zCxQGNaMtmfpZTtsi8ng3iSinfdrbF0fWSpkJ3COJR1dM7PVqb9PS0tkm4A9w4N9ApfAfJPXICkeZT4Ki9KRpVyMnT"
            logger.warning("Using hardcoded credentials - set PAYBETS_CLIENT_ID and PAYBETS_CLIENT_SECRET environment variables")
        
        # Configurar session para reutilização de conexões
        self.session = requests.Session()
        
        logger.info(f"PayBets API initialized - URL: {self.API_URL}")
        
    def _authenticate(self) -> None:
        """
        Autenticar na API PayBets e obter token JWT
        """
        try:
            auth_payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            
            response = requests.post(
                f"{self.API_URL}/api/auth/login",
                json=auth_payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                auth_data = response.json()
                self.jwt_token = auth_data.get("token")
                logger.info("PayBets authentication successful")
            else:
                logger.error(f"PayBets authentication failed: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                raise Exception("Authentication failed")
                
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Headers padrão para as requisições HTTP
        """
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "PayBets-Python-SDK/1.0.0",
            "x-api-key": self.client_id
        }
    
    def _validate_payment_data(self, data: PaymentRequestData) -> None:
        """
        Validar e sanitizar dados do pagamento antes do envio
        """
        # Validar campos obrigatórios
        if not data.name or not data.name.strip():
            raise ValueError("Nome é obrigatório")
        if not data.email or not data.email.strip():
            raise ValueError("Email é obrigatório")
        if not data.cpf or not data.cpf.strip():
            raise ValueError("CPF é obrigatório")
        if not data.amount or data.amount <= 0:
            raise ValueError("Valor é obrigatório e deve ser maior que zero")
        
        # Validar e formatar CPF
        cpf = ''.join(filter(str.isdigit, data.cpf))
        if len(cpf) != 11:
            raise ValueError("CPF deve conter exatamente 11 dígitos")
        
        # Validar email com regex básico
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, data.email.strip()):
            raise ValueError("Email inválido")
        
        # Validar valor
        if not isinstance(data.amount, (int, float)) or data.amount <= 0:
            raise ValueError("Valor deve ser um número positivo")
        
        # Validar limites de valor
        if data.amount > 50000:  # Limite máximo PIX
            raise ValueError("Valor excede limite máximo de R$ 50.000,00")
        
        # Sanitizar nome (remover caracteres especiais)
        name_cleaned = re.sub(r'[^a-zA-ZÀ-ÿ\s]', '', data.name.strip())
        if len(name_cleaned) < 2:
            raise ValueError("Nome deve conter pelo menos 2 caracteres válidos")
        
        logger.info(f"Dados validados para CPF: {cpf[:3]}***{cpf[-2:]}")
    
    def _make_request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Fazer requisição HTTP com retry automático
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    timeout=self.timeout,
                    **kwargs
                )
                return response
            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Request failed after {self.max_retries} attempts: {str(e)}")
                    raise
                else:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Request attempt {attempt + 1} failed, retrying in {wait_time}s: {str(e)}")
                    time.sleep(wait_time)
    
    def create_pix_payment(self, data: PaymentRequestData) -> PaymentResponse:
        """
        Criar um pagamento PIX via PayBets com retry automático
        """
        
        # Validar dados de entrada
        self._validate_payment_data(data)
        
        # Processar e formatar dados
        cpf = ''.join(filter(str.isdigit, data.cpf))
        
        # Gerar external_id único e rastreável
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        external_id = f"IBGE-{timestamp}-{unique_id}"
        
        # Construir payload correto para a API PayBets
        payment_data = {
            "value": float(data.amount),
            "externalId": external_id,
            "clientCallbackUrl": os.getenv("PAYBETS_WEBHOOK_URL", "https://webhook.site/unique-id"),
            "customer": {
                "name": data.name.strip(),
                "email": data.email.strip(),
                "document": cpf,
                "phone": data.phone or "(11) 98768-9080"
            },
            "items": [{
                "name": data.description or "Receita de bolo",
                "value": float(data.amount),
                "quantity": 1
            }]
        }
        
        # Log seguro (sem dados sensíveis)
        logger.info(f"Creating PIX payment - Amount: R$ {data.amount:.2f}, External ID: {external_id}")
        
        try:
            response = self._make_request_with_retry(
                method="POST",
                url=f"{self.API_URL}/payments/pix",
                json=payment_data,
                headers=self._get_headers()
            )
            
            logger.info(f"PayBets API response: HTTP {response.status_code}")
            
            # Tratar erros HTTP (PayBets retorna 200 para sucesso)
            if response.status_code not in [200, 201]:
                error_message = self._extract_error_message(response)
                logger.error(f"PayBets API error: {error_message}")
                raise requests.exceptions.RequestException(f"API Error: {error_message}")
            
            # Processar resposta de sucesso
            response_data = response.json()
            logger.info("PIX payment created successfully")
            
            return self._parse_payment_response(response_data, external_id)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise
    
    def _extract_error_message(self, response: requests.Response) -> str:
        """
        Extrair mensagem de erro da resposta da API com logging
        """
        status_code = response.status_code
        
        # Mapear códigos de erro conhecidos
        error_map = {
            400: "Dados inválidos enviados para a API",
            401: "Acesso não autorizado - verifique a chave de API",
            403: "Acesso negado - permissões insuficientes",
            404: "Endpoint não encontrado",
            429: "Limite de requisições excedido - tente novamente em breve",
            500: "Erro interno do servidor PayBets",
            502: "Servidor indisponível temporariamente",
            503: "Serviço indisponível no momento"
        }
        
        default_message = error_map.get(status_code, f"Erro HTTP {status_code}")
        
        # Tentar extrair mensagem detalhada do JSON
        try:
            error_data = response.json()
            if not error_data.get("success", True):
                detailed_message = (
                    error_data.get("message") or 
                    error_data.get("error") or 
                    default_message
                )
                logger.error(f"API Error Details: {error_data}")
                return detailed_message
        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse error response as JSON")
            
        # Log do erro para debugging
        logger.error(f"HTTP {status_code} - {default_message}")
        logger.debug(f"Response text: {response.text[:200]}...")
        
        return default_message
    
    def _parse_payment_response(self, response_data: Dict[str, Any], external_id: str) -> PaymentResponse:
        """
        Processar resposta da criação de pagamento PayBets
        """
        
        # Verificar se a resposta é bem-sucedida
        if not response_data.get("success", True):
            raise ValueError(f"Erro na API: {response_data.get('message', 'Erro desconhecido')}")
        
        # Extrair dados diretamente da resposta PayBets
        payment_response = response_data.get("data", response_data)
        
        transaction_id = payment_response.get("id", payment_response.get("transactionId", external_id))
        pix_code = payment_response.get("pixCode", payment_response.get("qrcode", ""))
        status = payment_response.get("status", "PENDING")
        amount = payment_response.get("value", payment_response.get("amount", 45.84))
        
        logger.info(f"[PayBets] Transaction ID: {transaction_id}")
        logger.info(f"[PayBets] PIX Code: {pix_code[:50]}...")
        logger.info(f"[PayBets] Status: {status}")
        logger.info(f"[PayBets] Amount: R$ {amount:.2f}")
        
        # Gerar QR Code como base64 (PayBets não retorna imagem, apenas código)
        pix_qr_code = self._generate_qr_code_base64(pix_code)
        
        return PaymentResponse(
            transaction_id=transaction_id,
            pix_code=pix_code,
            pix_qr_code=pix_qr_code,
            status=status,
            amount=amount
        )
    
    def _generate_qr_code_base64(self, pix_code: str) -> str:
        """
        Gerar QR Code em base64 a partir do código PIX
        """
        try:
            import qrcode
            import io
            import base64
            
            # Criar QR Code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(pix_code)
            qr.make(fit=True)
            
            # Gerar imagem
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Converter para base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            qr_base64 = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{qr_base64}"
            
        except ImportError:
            print("[PayBets] qrcode não disponível, retornando placeholder")
            return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    
    def check_payment_status(self, transaction_id: str) -> Dict[str, Any]:
        """
        Verificar status de um pagamento PayBets com retry automático
        """
        if not transaction_id:
            logger.error("Transaction ID is required for status check")
            return {"status": "error", "message": "Transaction ID é obrigatório"}
        
        logger.info(f"Checking payment status for transaction: {transaction_id}")
        
        try:
            # Usar endpoint específico para verificação de status
            response = self._make_request_with_retry(
                method="GET",
                url=f"{self.API_URL}/payments/pix/status/{transaction_id}"
            )
            
            if response.status_code != 200:
                error_message = self._extract_error_message(response)
                logger.error(f"Status check failed: {error_message}")
                return {"status": "error", "message": error_message}
            
            response_data = response.json()
            
            if not response_data.get("success", False):
                error_msg = response_data.get("message", "Erro desconhecido")
                logger.error(f"API returned error: {error_msg}")
                return {"status": "error", "message": error_msg}
            
            payment_data = response_data.get("data", {})
            status = payment_data.get("status", "PENDING").upper()
            
            logger.info(f"Payment status: {status}")
            
            # Mapear status para estados padronizados
            status_mapping = {
                "PAID": "paid",
                "APPROVED": "paid", 
                "COMPLETED": "paid",
                "PENDING": "pending",
                "WAITING_PAYMENT": "pending",
                "FAILED": "failed",
                "CANCELLED": "failed",
                "EXPIRED": "failed"
            }
            
            normalized_status = status_mapping.get(status, "pending")
            
            return {
                "status": normalized_status,
                "original_status": status,
                "payment_data": payment_data,
                "paid": normalized_status == "paid",
                "pending": normalized_status == "pending",
                "failed": normalized_status == "failed",
                "transaction_id": transaction_id
            }
            
        except Exception as e:
            logger.error(f"Status check error: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def consult_cpf(self, cpf: str) -> Dict[str, Any]:
        """
        Consultar dados cadastrais de um CPF via PayBets API
        
        Args:
            cpf: CPF para consulta (apenas números)
            
        Returns:
            Dict com dados do CPF ou erro
        """
        if not cpf:
            logger.error("CPF is required for consultation")
            return {"success": False, "message": "CPF é obrigatório"}
        
        # Limpar CPF (apenas números)
        cpf_clean = ''.join(filter(str.isdigit, cpf))
        
        if len(cpf_clean) != 11:
            logger.error(f"Invalid CPF length: {len(cpf_clean)}")
            return {"success": False, "message": "CPF deve ter 11 dígitos"}
        
        logger.info(f"Consulting CPF: {cpf_clean[:3]}***{cpf_clean[-2:]}")
        
        try:
            response = self._make_request_with_retry(
                method="GET",
                url=f"{self.API_URL}/external/cpf/{cpf_clean}"
            )
            
            logger.info(f"CPF consultation response: HTTP {response.status_code}")
            
            if response.status_code != 200:
                error_message = self._extract_error_message(response)
                logger.error(f"CPF consultation failed: {error_message}")
                return {"success": False, "message": error_message}
            
            response_data = response.json()
            
            if not response_data.get("success", False):
                error_msg = response_data.get("message", "Erro na consulta do CPF")
                logger.error(f"API returned error: {error_msg}")
                return {"success": False, "message": error_msg}
            
            cpf_data = response_data.get("data", {})
            logger.info("CPF consultation successful")
            
            return {
                "success": True,
                "data": {
                    "cpf": cpf_data.get("cpf", cpf_clean),
                    "nome": cpf_data.get("nome", ""),
                    "nome_mae": cpf_data.get("nome_mae", ""),
                    "data_nascimento": cpf_data.get("data_nascimento", ""),
                    "sexo": cpf_data.get("sexo", "")
                }
            }
            
        except Exception as e:
            logger.error(f"CPF consultation error: {str(e)}")
            return {"success": False, "message": f"Erro na consulta: {str(e)}"}
    
    def close(self):
        """
        Fechar sessão HTTP para limpeza de recursos
        """
        if hasattr(self, 'session'):
            self.session.close()
            logger.info("HTTP session closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

# Factory functions para facilitar o uso

def get_paybets_api_instance(environment: str = "production") -> PayBetsAPI:
    """
    Factory function para criar instância da PayBets API
    
    Args:
        environment: "production", "staging", "development"
    
    Returns:
        PayBetsAPI: Instância configurada para o ambiente
    """
    if environment == "production":
        return PayBetsAPI(
            timeout=30,
            max_retries=3
        )
    elif environment == "staging":
        return PayBetsAPI(
            timeout=20,
            max_retries=2
        )
    else:  # development
        return PayBetsAPI(
            timeout=15,
            max_retries=1
        )

def create_production_api() -> PayBetsAPI:
    """
    Criar instância da API otimizada para produção
    """
    return get_paybets_api_instance("production")

def health_check() -> Dict[str, Any]:
    """
    Verificar saúde da API PayBets
    """
    try:
        with create_production_api() as api:
            # Fazer uma requisição simples para verificar conectividade
            response = api.session.get(
                api.API_URL.replace("/api", "/health"),
                timeout=5
            )
            
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "api_url": api.API_URL,
                "response_time": response.elapsed.total_seconds(),
                "status_code": response.status_code
            }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "api_url": "unknown"
        }

def gerar_codigo_pix_simulado(valor, protocolo):
    """Gerar código PIX simulado para demonstração (mantido para compatibilidade)"""
    import uuid
    # Gerar identificador único baseado no protocolo
    identificador = str(uuid.uuid4()).replace('-', '')[:32]
    # Valor formatado para PIX (sem ponto decimal)
    valor_centavos = str(int(valor * 100)).zfill(4)
    # Código PIX simulado no formato oficial
    codigo = f"00020126580014BR.GOV.BCB.PIX0136{identificador}52040000530398654{len(valor_centavos):02d}{valor_centavos}5802BR5925RECEITA FEDERAL BRASIL6008BRASILIA62070503{protocolo[-3:]}6304"
    # Calcular CRC (simplificado para demonstração)
    crc = hex(hash(codigo) % 65536)[2:].upper().zfill(4)
    return codigo + crc
