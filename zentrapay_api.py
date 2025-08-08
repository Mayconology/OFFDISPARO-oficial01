
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
class ZentraPaymentData:
    """Estrutura de dados para pagamento ZentraPay"""
    name: str
    email: str
    cpf: str
    phone: str
    amount: float
    description: str = "Receita de bolo"

@dataclass
class ZentraPayResponse:
    """Estrutura de resposta ZentraPay"""
    transaction_id: str
    pix_code: str
    pix_qr_code: str
    status: str
    amount: float
    expires_at: str

class ZentraPayAPI:
    """
    Cliente para API ZentraPay BR - Implementação Production-Ready
    
    Funcionalidades:
    - Autenticação via API Key
    - Geração de PIX real via ZentraPay
    - Verificação de status
    - Tratamento de erros robusto
    - QR Code base64 automático
    - Webhook support
    """

    def __init__(self, api_key: Optional[str] = None, timeout: int = 30, max_retries: int = 3):
        """
        Inicializar cliente ZentraPay API

        Args:
            api_key: API Key da ZentraPay (se None, busca em variável de ambiente)
            timeout: Timeout para requisições em segundos
            max_retries: Número máximo de tentativas em caso de falha
        """
        # URL oficial da ZentraPay conforme documentação
        self.API_URL = "https://api.zentrapaybr.com"
        self.timeout = timeout
        self.max_retries = max_retries

        # Configurar credenciais ZentraPay
        self.api_key = api_key or os.getenv("ZENTRAPAY_API_KEY", "sk_a7da0a8cfc7bac4836572ab2068fd3059493dd63a97ab76ceb5dd46b50a9941f654da937b48ae2a4ded1468217c0291be0eccc264ecd9e92ca9eff27231c968e")

        # Configurar session para reutilização de conexões
        self.session = requests.Session()
        self.session.headers.update(self._get_headers())

        logger.info(f"ZentraPay API initialized - URL: {self.API_URL}")
        logger.info(f"ZentraPay credentials configured - Key: {self.api_key[:10]}***")

    def _get_headers(self) -> Dict[str, str]:
        """
        Headers padrão para as requisições HTTP
        """
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "ZentraPay-Python-SDK/1.0.0"
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

    def _generate_transaction_id(self) -> str:
        """Gerar ID único para transação"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        return f"ZENTRA-{timestamp}-{unique_id}"

    def create_pix_payment(self, data: ZentraPaymentData) -> ZentraPayResponse:
        """
        Criar pagamento PIX via ZentraPay API

        Args:
            data: Dados do pagamento (ZentraPaymentData)

        Returns:
            ZentraPayResponse com dados do PIX gerado

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

        # Limpar telefone
        phone = ''.join(filter(str.isdigit, data.phone)) if data.phone else "11987679080"
        if len(phone) < 10:
            phone = "11987679080"

        # Gerar ID único para a transação
        external_id = self._generate_transaction_id()

        # Construir payload conforme documentação ZentraPay
        payment_data = {
            "amount": float(data.amount),
            "currency": "BRL",
            "payment_method": "pix",
            "external_id": external_id,
            "description": data.description,
            "customer": {
                "name": data.name.strip(),
                "email": data.email.strip(),
                "document": {
                    "type": "cpf",
                    "number": cpf
                },
                "phone": phone
            },
            "notification_url": os.getenv("ZENTRAPAY_WEBHOOK_URL", "https://webhook.site/zentrapay-callback"),
            "expires_in": 3600  # 1 hora
        }

        # Log seguro (sem dados sensíveis)
        logger.info(f"Creating PIX payment - Amount: R$ {data.amount:.2f}, External ID: {external_id}")
        logger.info(f"Customer: {data.name} - Document: {cpf[:3]}***{cpf[-2:]}")

        try:
            response = self._make_request_with_retry(
                method="POST",
                url=f"{self.API_URL}/v1/payments",
                json=payment_data
            )

            logger.info(f"ZentraPay API response: HTTP {response.status_code}")

            # Tratar erros HTTP
            if response.status_code not in [200, 201]:
                error_message = self._extract_error_message(response)
                logger.error(f"ZentraPay API error: {error_message}")
                raise requests.exceptions.RequestException(f"API Error: {error_message}")

            # Processar resposta de sucesso
            response_data = response.json()
            logger.info(f"ZentraPay API raw response: {json.dumps(response_data, indent=2)}")
            
            if not response_data.get('success', True):
                error_msg = response_data.get('message', 'Unknown error')
                logger.error(f"ZentraPay API returned success=false: {error_msg}")
                raise requests.exceptions.RequestException(f"ZentraPay Error: {error_msg}")

            logger.info("PIX payment created successfully via ZentraPay")
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
            transaction_id: ID da transação ZentraPay

        Returns:
            Dict com status do pagamento
        """
        try:
            response = self._make_request_with_retry(
                method="GET",
                url=f"{self.API_URL}/v1/payments/{transaction_id}"
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
            
            status = response_data.get('status', 'unknown')
            
            return {
                'status': status,
                'transaction_id': transaction_id,
                'paid': status in ['paid', 'completed', 'approved'],
                'pending': status in ['pending', 'waiting_payment'],
                'failed': status in ['failed', 'expired', 'cancelled', 'refunded'],
                'amount': response_data.get('amount', 0),
                'paid_at': response_data.get('paid_at'),
                'created_at': response_data.get('created_at')
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
            if 'error' in error_data:
                if isinstance(error_data['error'], dict):
                    return error_data['error'].get('message', f'HTTP {response.status_code}')
                return str(error_data['error'])
            return error_data.get('message', f'HTTP {response.status_code}')
        except:
            pass

        # Mensagens padrão por código de status
        status_messages = {
            400: "Dados inválidos ou campos obrigatórios ausentes",
            401: "Acesso não autorizado - verifique a API key",
            403: "Acesso negado - verifique as permissões",
            404: "Recurso não encontrado",
            422: "Dados não processáveis - verifique o formato",
            429: "Muitas requisições - limite de rate limit atingido",
            500: "Erro interno do servidor ZentraPay"
        }

        return status_messages.get(response.status_code, f"HTTP {response.status_code}")

    def _parse_payment_response(self, response_data: Dict[str, Any], original_amount: float) -> ZentraPayResponse:
        """
        Processar resposta da criação de transação ZentraPay
        """
        # Extrair dados conforme documentação ZentraPay
        payment_data = response_data.get("data", response_data)
        pix_data = payment_data.get("pix", {})

        transaction_id = payment_data.get("id", payment_data.get("transaction_id", ""))
        pix_code = (
            pix_data.get("qr_code", "") or 
            pix_data.get("pix_code", "") or 
            pix_data.get("code", "") or
            payment_data.get("qr_code", "") or
            payment_data.get("pix_code", "")
        )
        status = payment_data.get("status", "pending")
        amount = payment_data.get("amount", original_amount)
        expires_at = payment_data.get("expires_at", pix_data.get("expires_at", ""))

        logger.info(f"[ZentraPay] Transaction ID: {transaction_id}")
        logger.info(f"[ZentraPay] PIX Code length: {len(pix_code) if pix_code else 0}")
        logger.info(f"[ZentraPay] PIX Code preview: {pix_code[:50]}...")
        logger.info(f"[ZentraPay] Status: {status}")
        logger.info(f"[ZentraPay] Amount: R$ {amount:.2f}")
        logger.info(f"[ZentraPay] Expires: {expires_at}")

        # Validar campos obrigatórios
        if not transaction_id:
            logger.error("[ZentraPay] Transaction ID is empty!")
            raise ValueError("ZentraPay não retornou transaction_id válido")

        if not pix_code:
            logger.error("[ZentraPay] PIX Code is empty!")
            raise ValueError("ZentraPay não retornou código PIX válido")

        # Gerar QR Code como base64
        pix_qr_code = self._generate_qr_code_base64(pix_code) if pix_code else ""

        response = ZentraPayResponse(
            transaction_id=transaction_id,
            pix_code=pix_code,
            pix_qr_code=pix_qr_code,
            status=status,
            amount=amount,
            expires_at=expires_at
        )

        logger.info(f"[ZentraPay] Response object created successfully")
        return response

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

def create_zentrapay_api(api_key: str = None) -> ZentraPayAPI:
    """
    Factory function para criar instância da API ZentraPay
    """
    return ZentraPayAPI(
        api_key=api_key,
        timeout=30,
        max_retries=3
    )

def health_check() -> Dict[str, Any]:
    """
    Verificar saúde da API ZentraPay
    """
    try:
        api = ZentraPayAPI()
        # Fazer uma requisição simples para testar conectividade
        response = requests.get(f"{api.API_URL}/v1/health", timeout=10)
        
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
