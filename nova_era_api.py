
import os
import json
import requests
import uuid
import qrcode
import io
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class NovaEraPaymentData:
    """Estrutura de dados para pagamento Nova Era"""
    name: str
    email: str
    cpf: str
    phone: str
    amount: float
    description: str = "Receita de bolo"

@dataclass
class NovaEraResponse:
    """Estrutura de resposta Nova Era"""
    transaction_id: str
    pix_code: str
    pix_qr_code: str
    status: str
    amount: float
    expires_at: str

class NovaEraAPI:
    """
    Cliente para API Nova Era Pagamentos - Implementação Production-Ready
    
    Funcionalidades:
    - Autenticação Basic Auth automática
    - Geração de PIX real via Nova Era
    - Verificação de status
    - Tratamento de erros robusto
    - QR Code base64 automático
    - Webhook support
    """

    def __init__(self, secret_key: Optional[str] = None, public_key: Optional[str] = None, 
                 timeout: int = 30, max_retries: int = 3):
        """
        Inicializar cliente Nova Era API

        Args:
            secret_key: Secret Key da Nova Era (se None, busca em variável de ambiente)
            public_key: Public Key da Nova Era (se None, busca em variável de ambiente)
            timeout: Timeout para requisições em segundos
            max_retries: Número máximo de tentativas em caso de falha
        """
        # URL oficial da Nova Era conforme documentação
        self.API_URL = "https://api.novaera-pagamentos.com/api/v1"
        self.timeout = timeout
        self.max_retries = max_retries

        # Configurar credenciais Nova Era
        self.secret_key = secret_key or os.getenv("NOVA_ERA_SECRET_KEY", "sk_uluAT1O9I6FGTQAcXzccr2H_eAQ9IOzYoY_LLDfR8U6Uv2Xb")
        self.public_key = public_key or os.getenv("NOVA_ERA_PUBLIC_KEY", "pk_E5SWGB_rZ-mZowMITdSr5w8zhOdY8TDImLhOM-s9gmJPoc9x")

        # Configurar session para reutilização de conexões
        self.session = requests.Session()
        self.session.headers.update(self._get_headers())

        logger.info(f"Nova Era API initialized - URL: {self.API_URL}")
        logger.info(f"Nova Era credentials configured - Secret: {self.secret_key[:10]}***")

    def _get_headers(self) -> Dict[str, str]:
        """
        Headers padrão para as requisições HTTP
        """
        # Gerar token Basic Auth
        credentials = f"{self.secret_key}:{self.public_key}"
        token = base64.b64encode(credentials.encode()).decode()
        
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Basic {token}",
            "User-Agent": "NovaEra-Python-SDK/1.0.0"
        }

    def _make_request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Fazer requisição HTTP com retry automático
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                return response

            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Request failed after {self.max_retries} attempts: {str(e)}")
                    raise
                else:
                    logger.warning(f"Request attempt {attempt + 1} failed: {str(e)}, retrying...")
                    continue

    def _validate_cpf(self, cpf: str) -> str:
        """
        Validar e limpar CPF (remove pontos e hífens)
        """
        if not cpf:
            raise ValueError("CPF é obrigatório")

        # Limpar CPF (remover pontos, hífens e espaços)
        cpf_clean = ''.join(filter(str.isdigit, cpf))

        if len(cpf_clean) != 11:
            raise ValueError("CPF deve ter 11 dígitos")

        logger.info(f"CPF validado: {cpf_clean[:3]}***{cpf_clean[-2:]}")
        return cpf_clean

    def create_pix_payment(self, data: NovaEraPaymentData) -> NovaEraResponse:
        """
        Criar pagamento PIX via Nova Era API

        Args:
            data: Dados do pagamento (NovaEraPaymentData)

        Returns:
            NovaEraResponse com dados do PIX gerado

        Raises:
            ValueError: Para dados inválidos
            requests.exceptions.RequestException: Para erros de API
        """
        # Validar dados de entrada
        if not all([data.name, data.email, data.cpf, data.amount]):
            raise ValueError("Todos os campos são obrigatórios: name, email, cpf, amount")

        if data.amount <= 0:
            raise ValueError("Valor deve ser maior que zero")

        # Validar e limpar CPF
        cpf = self._validate_cpf(data.cpf)

        # Converter valor para centavos (padrão Nova Era)
        amount_cents = int(data.amount * 100)

        # Construir payload conforme documentação Nova Era
        payment_data = {
            "customer": {
                "name": data.name.strip(),
                "email": data.email.strip(),
                "phone": data.phone.strip() if data.phone else "(11) 98768-9080",
                "document": {
                    "number": cpf,
                    "type": "cpf"
                }
            },
            "items": [
                {
                    "tangible": False,
                    "quantity": 1,
                    "unitPrice": amount_cents,
                    "title": data.description
                }
            ],
            "postbackUrl": os.getenv("NOVA_ERA_WEBHOOK_URL", "https://webhook.site/nova-era-callback"),
            "amount": amount_cents,
            "paymentMethod": "pix"
        }

        # Log seguro (sem dados sensíveis)
        logger.info(f"Creating PIX payment - Amount: R$ {data.amount:.2f} ({amount_cents} cents)")
        logger.info(f"Customer: {data.name} - Document: {cpf[:3]}***{cpf[-2:]}")

        try:
            response = self._make_request_with_retry(
                method="POST",
                url=f"{self.API_URL}/transactions",
                json=payment_data
            )

            logger.info(f"Nova Era API response: HTTP {response.status_code}")

            # Tratar erros HTTP
            if response.status_code not in [200, 201]:
                error_message = self._extract_error_message(response)
                logger.error(f"Nova Era API error: {error_message}")
                raise requests.exceptions.RequestException(f"API Error: {error_message}")

            # Processar resposta de sucesso
            response_data = response.json()
            logger.info("PIX payment created successfully via Nova Era")

            if not response_data.get('success', False):
                error_msg = response_data.get('error', {}).get('message', 'Unknown error')
                raise requests.exceptions.RequestException(f"Nova Era Error: {error_msg}")

            return self._parse_payment_response(response_data, data.amount)

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise

    def check_payment_status(self, transaction_id: str) -> Dict[str, Any]:
        """
        Verificar status do pagamento

        Args:
            transaction_id: ID da transação Nova Era

        Returns:
            Dict com status do pagamento
        """
        try:
            response = self._make_request_with_retry(
                method="GET",
                url=f"{self.API_URL}/transactions/{transaction_id}"
            )

            if response.status_code == 404:
                return {
                    'status': 'not_found',
                    'transaction_id': transaction_id,
                    'paid': False,
                    'pending': False,
                    'failed': True
                }

            if response.status_code != 200:
                return {
                    'status': 'error',
                    'error': f'HTTP {response.status_code}',
                    'transaction_id': transaction_id
                }

            response_data = response.json()
            
            if response_data.get('success', False):
                transaction_data = response_data.get('data', {})
                status = transaction_data.get('status', 'unknown')
                
                return {
                    'status': status,
                    'transaction_id': transaction_id,
                    'paid': status == 'paid',
                    'pending': status == 'waiting_payment',
                    'failed': status in ['failed', 'expired', 'cancelled'],
                    'amount': transaction_data.get('amount', 0) / 100,  # Converter de centavos
                    'paid_at': transaction_data.get('paid_at'),
                    'created_at': transaction_data.get('created_at')
                }
            else:
                return {
                    'status': 'error',
                    'error': response_data.get('error', {}).get('message', 'Unknown error'),
                    'transaction_id': transaction_id
                }

        except Exception as e:
            logger.error(f"Error checking payment status: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'transaction_id': transaction_id
            }

    def _extract_error_message(self, response: requests.Response) -> str:
        """
        Extrair mensagem de erro da resposta HTTP
        """
        try:
            error_data = response.json()
            if 'error' in error_data and isinstance(error_data['error'], dict):
                return error_data['error'].get('message', f'HTTP {response.status_code}')
            return error_data.get('message', f'HTTP {response.status_code}')
        except:
            pass

        # Mensagens padrão por código de status
        status_messages = {
            400: "Dados inválidos ou campos obrigatórios ausentes",
            401: "Acesso não autorizado - verifique as chaves de API",
            403: "Acesso negado - verifique as permissões",
            404: "Recurso não encontrado",
            429: "Muitas requisições - limite de rate limit atingido",
            500: "Erro interno do servidor Nova Era"
        }

        return status_messages.get(response.status_code, f"HTTP {response.status_code}")

    def _parse_payment_response(self, response_data: Dict[str, Any], original_amount: float) -> NovaEraResponse:
        """
        Processar resposta da criação de transação Nova Era
        """
        # Extrair dados conforme documentação Nova Era
        transaction_data = response_data.get("data", {})
        pix_data = transaction_data.get("pix", {})

        transaction_id = transaction_data.get("id", "")
        pix_code = pix_data.get("qrcode", "")
        status = transaction_data.get("status", "waiting_payment")
        amount = transaction_data.get("amount", 0) / 100  # Converter de centavos
        expires_at = pix_data.get("expires_at", "")

        logger.info(f"[Nova Era] Transaction ID: {transaction_id}")
        logger.info(f"[Nova Era] PIX Code: {pix_code[:50]}...")
        logger.info(f"[Nova Era] Status: {status}")
        logger.info(f"[Nova Era] Amount: R$ {amount:.2f}")
        logger.info(f"[Nova Era] Expires: {expires_at}")

        # Gerar QR Code como base64
        pix_qr_code = self._generate_qr_code_base64(pix_code) if pix_code else ""

        return NovaEraResponse(
            transaction_id=transaction_id,
            pix_code=pix_code,
            pix_qr_code=pix_qr_code,
            status=status,
            amount=amount,
            expires_at=expires_at
        )

    def _generate_qr_code_base64(self, pix_code: str) -> str:
        """
        Gerar QR Code em base64 a partir do código PIX
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(pix_code)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            # Converter para base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()

            return f"data:image/png;base64,{img_str}"

        except Exception as e:
            logger.error(f"Error generating QR code: {str(e)}")
            return ""

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if hasattr(self, 'session') and self.session:
            self.session.close()

# Funções auxiliares para compatibilidade

def create_nova_era_api(secret_key: str = None, public_key: str = None) -> NovaEraAPI:
    """
    Factory function para criar instância da API Nova Era
    """
    return NovaEraAPI(
        secret_key=secret_key,
        public_key=public_key,
        timeout=30,
        max_retries=3
    )

def health_check() -> Dict[str, Any]:
    """
    Verificar saúde da API Nova Era
    """
    try:
        api = NovaEraAPI()
        # Fazer uma requisição simples para testar conectividade
        response = requests.get(f"{api.API_URL}/health", timeout=10)
        
        return {
            'status': 'healthy' if response.status_code == 200 else 'unhealthy',
            'api_url': api.API_URL,
            'response_time': response.elapsed.total_seconds(),
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }
