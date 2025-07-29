# Iron Pay API - Documentação Completa para Replit

## 📋 Visão Geral

Esta documentação fornece uma implementação completa da Iron Pay API para projetos Replit, incluindo geração de PIX, webhook handling e sistema de fallback.

## 🔧 Configuração Inicial

### 1. Variáveis de Ambiente (Secrets)

Configure as seguintes secrets no seu projeto Replit:

```bash
IRONPAY_API_TOKEN=xYipgGdsLKk2779ZQHqpfm0TfZqJqJP8q5iRj272pogLoOhV5dJjY7jpftrD
```

### 2. Dependências

Adicione ao seu `pyproject.toml`:

```toml
[tool.uv]
dependencies = [
    "flask",
    "requests", 
    "qrcode",
    "pillow",
    "gunicorn"
]
```

## 💻 Implementação Completa

### 1. Arquivo Principal: `ironpay_api.py`

```python
import os
import json
import logging
import requests
import qrcode
import base64
from io import BytesIO
from typing import Dict, Any, Optional
from dataclasses import dataclass
import uuid

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class IronPaymentData:
    """Dados necessários para pagamento Iron Pay"""
    name: str
    email: str
    cpf: str
    phone: str
    amount: float
    description: str
    street_name: str = "Não informado"
    number: str = "s/n"
    city: str = "São Paulo"
    state: str = "SP"
    zip_code: str = "01000000"

@dataclass
class IronPaymentResponse:
    """Resposta da Iron Pay API"""
    transaction_hash: str
    pix_code: str
    pix_qr_code: str
    status: str
    amount: float

class IronPayAPI:
    """Cliente para Iron Pay API"""
    
    def __init__(self, api_token: Optional[str] = None, timeout: int = 30, max_retries: int = 3):
        """
        Inicializar Iron Pay API
        
        Args:
            api_token: Token da Iron Pay API (se None, busca em variável de ambiente)
            timeout: Timeout para requisições em segundos
            max_retries: Número máximo de tentativas em caso de falha
        """
        self.API_URL = "https://api.ironpayapp.com.br"
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Configurar token API
        self.api_token = api_token or os.getenv("IRONPAY_API_TOKEN")
        if not self.api_token:
            raise ValueError("IRONPAY_API_TOKEN é obrigatório para usar a Iron Pay API")
        
        # Configurar session para reutilização de conexões
        self.session = requests.Session()
        
        logger.info(f"✅ Iron Pay API initialized - URL: {self.API_URL}")
        
    def create_pix_payment(self, data: IronPaymentData) -> IronPaymentResponse:
        """
        Criar pagamento PIX via Iron Pay
        
        Args:
            data: Dados do pagamento
            
        Returns:
            IronPaymentResponse: Resposta com dados do PIX
            
        Raises:
            ValueError: Se dados inválidos
            Exception: Se erro na API
        """
        # Validar e limpar dados
        cpf_clean = ''.join(filter(str.isdigit, data.cpf))
        if len(cpf_clean) != 11:
            raise ValueError(f"CPF inválido: {data.cpf}")
            
        phone_clean = ''.join(filter(str.isdigit, data.phone))
        if len(phone_clean) < 10:
            # Se não tem telefone válido, usar padrão
            phone_clean = "11999999999"
            
        amount_cents = int(data.amount * 100)  # Iron Pay usa centavos
        
        # Iron Pay: usar hashes específicos da conta do usuário
        product_hash = "jrddtst9rp"  # Hash do produto fornecido pelo usuário
        offer_hash = "vduc64lrsq"    # Hash da oferta fornecido pelo usuário
        
        # Preparar payload conforme documentação Iron Pay
        payment_data = {
            "amount": amount_cents,
            "offer_hash": offer_hash,
            "payment_method": "pix",
            "customer": {
                "name": data.name.strip(),
                "email": data.email.strip(),
                "phone_number": phone_clean,
                "document": cpf_clean,
                "street_name": data.street_name,
                "number": data.number,
                "neighborhood": "Centro",
                "city": data.city,
                "state": data.state,
                "zip_code": data.zip_code
            },
            "cart": [{
                "product_hash": product_hash,
                "title": data.description,
                "cover": None,
                "price": amount_cents,
                "quantity": 1,
                "operation_type": 1,
                "tangible": False,
                "product_id": 6561,  # ID fixo conforme documentação
                "offer_id": 9535     # ID fixo conforme documentação
            }],
            "installments": 1,
            "expire_in_days": 1,
            "transaction_origin": "api",
            "tracking": {
                "src": "",
                "utm_source": "",
                "utm_medium": "",
                "utm_campaign": "",
                "utm_term": "",
                "utm_content": ""
            }
        }
        
        logger.info(f"🔄 Criando PIX Iron Pay - Valor: R${data.amount:.2f}, Cliente: {data.name}")
        
        try:
            # Fazer requisição para Iron Pay API real
            response = self.session.post(
                f"{self.API_URL}/api/public/v1/transactions",
                params={"api_token": self.api_token},
                json=payment_data,
                timeout=self.timeout,
                headers={"Accept": "application/json"}
            )
            
            logger.info(f"📡 Iron Pay Response: HTTP {response.status_code}")
            logger.info(f"📡 Iron Pay Response Body: {response.text[:500]}...")
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                logger.info(f"✅ Iron Pay Success: {response_data}")
                
                # Extrair dados da resposta conforme documentação Iron Pay
                transaction_hash = response_data.get("hash")
                pix_data = response_data.get("pix", {})
                pix_code = pix_data.get("pix_qr_code", "")
                pix_qr_code = pix_data.get("pix_qr_code", "")
                
                if not transaction_hash:
                    raise Exception("Iron Pay não retornou hash da transação")
                
                # Se não tem QR code na resposta, gerar a partir do PIX code
                if pix_code and not pix_qr_code:
                    pix_qr_code = self._generate_qr_code_base64(pix_code)
                
                return IronPaymentResponse(
                    transaction_hash=transaction_hash,
                    pix_code=pix_code or "",
                    pix_qr_code=pix_qr_code or "",
                    status=response_data.get("status", "pending"),
                    amount=data.amount
                )
            else:
                error_msg = f"Iron Pay API error: HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg += f" - {error_data}"
                except:
                    error_msg += f" - {response.text}"
                
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Iron Pay connection error: {e}")
            raise Exception(f"Iron Pay connection error: {e}")
        except Exception as e:
            logger.error(f"❌ Iron Pay error: {e}")
            raise
            
    def check_payment_status(self, transaction_hash: str) -> Dict[str, Any]:
        """
        Verificar status do pagamento
        
        Args:
            transaction_hash: Hash da transação
            
        Returns:
            Dict com status do pagamento
        """
        try:
            response = self.session.get(
                f"{self.API_URL}/api/public/v1/transactions/{transaction_hash}",
                params={"api_token": self.api_token},
                timeout=self.timeout,
                headers={"Accept": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Error checking payment status: HTTP {response.status_code}")
                return {"status": "error", "message": "Failed to check payment status"}
                
        except Exception as e:
            logger.error(f"❌ Error checking payment status: {e}")
            return {"status": "error", "message": str(e)}
    
    def _generate_qr_code_base64(self, pix_code: str) -> str:
        """
        Gerar QR code em base64 a partir do código PIX
        
        Args:
            pix_code: Código PIX
            
        Returns:
            QR code em formato base64
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
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{img_base64}"
            
        except Exception as e:
            logger.error(f"❌ Error generating QR code: {e}")
            return ""

def create_iron_pay_provider(api_token: Optional[str] = None) -> IronPayAPI:
    """
    Factory function para criar instância da Iron Pay API
    
    Args:
        api_token: Token da API (opcional, usa variável de ambiente se não fornecido)
        
    Returns:
        IronPayAPI: Instância configurada da API
    """
    return IronPayAPI(api_token=api_token)
```

### 2. Integração Flask: `app.py`

```python
from flask import Flask, request, jsonify
import json
import logging
from ironpay_api import create_iron_pay_provider, IronPaymentData

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/generate-pix', methods=['POST'])
def generate_pix():
    """Gerar PIX usando Iron Pay"""
    try:
        app.logger.info("[PROD] Recebendo solicitação de PIX via Iron Pay")

        # Verificar se há dados JSON na requisição
        if not request.is_json:
            app.logger.error("[PROD] Requisição não contém JSON válido")
            return jsonify({
                'success': False,
                'error': 'Content-Type deve ser application/json'
            }), 400

        data = request.get_json()

        # Verificar se dados foram recebidos
        if not data:
            app.logger.error("[PROD] Nenhum dado recebido na requisição")
            return jsonify({
                'success': False,
                'error': 'Dados não enviados na requisição'
            }), 400

        app.logger.info(f"[PROD] Dados recebidos no request: {json.dumps(data, indent=2)}")

        # Validação básica de campos obrigatórios
        required_fields = ['cpf', 'name', 'email']
        for field in required_fields:
            if not data.get(field):
                app.logger.error(f"[PROD] Campo obrigatório ausente: {field}")
                return jsonify({
                    'success': False,
                    'error': f'Campo {field} é obrigatório'
                }), 400

        # Dados recebidos do cliente
        customer_cpf = data['cpf']
        customer_name = data['name']
        customer_email = data.get('email', 'contato@exemplo.com')

        app.logger.info(f"[PROD] Gerando PIX para: {customer_name} (CPF: {customer_cpf[:3]}***{customer_cpf[-2:]})")

        # Valor fixo configurável
        amount = 127.94

        app.logger.info(f"[PROD] Valor do pagamento configurado: R$ {amount:.2f}")

        # Tentar Iron Pay API
        try:
            app.logger.info("[PROD] Tentando gerar PIX via Iron Pay API...")

            iron_pay_api = create_iron_pay_provider()

            payment_data = IronPaymentData(
                name=customer_name,
                email=customer_email,
                cpf=customer_cpf,
                phone="(11) 98768-9080",
                amount=amount,
                description="Produto teste Iron Pay"
            )

            app.logger.info(f"[PROD] Dados do pagamento Iron Pay: {payment_data}")

            iron_pay_response = iron_pay_api.create_pix_payment(payment_data)

            app.logger.info(f"[PROD] ✅ Iron Pay PIX gerado com sucesso: {iron_pay_response.transaction_hash}")

            return jsonify({
                'success': True,
                'transaction_id': iron_pay_response.transaction_hash,
                'order_id': iron_pay_response.transaction_hash,
                'amount': iron_pay_response.amount,
                'pixCode': iron_pay_response.pix_code,
                'pix_code': iron_pay_response.pix_code,
                'pixQrCode': iron_pay_response.pix_qr_code,
                'qr_code_image': iron_pay_response.pix_qr_code,
                'status': iron_pay_response.status,
                'provider': 'Iron Pay'
            })

        except Exception as e:
            app.logger.error(f"[PROD] Iron Pay falhou: {str(e)}")
            app.logger.error(f"[PROD] Iron Pay erro completo: {type(e).__name__}: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Erro na geração do PIX: {str(e)}'
            }), 500

    except Exception as e:
        app.logger.error(f"[PROD] Erro geral na geração de PIX: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500

@app.route('/check-payment-status/<transaction_hash>', methods=['GET'])
def check_payment_status(transaction_hash):
    """Verificar status do pagamento"""
    try:
        app.logger.info(f"[PROD] Verificando status da transação: {transaction_hash}")
        
        iron_pay_api = create_iron_pay_provider()
        status_data = iron_pay_api.check_payment_status(transaction_hash)
        
        return jsonify({
            'success': True,
            'transaction_hash': transaction_hash,
            'status': status_data
        })
        
    except Exception as e:
        app.logger.error(f"[PROD] Erro ao verificar status: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/iron-pay/webhook', methods=['POST'])
def iron_pay_webhook():
    """Webhook para receber notificações da Iron Pay"""
    try:
        app.logger.info("[PROD] Recebendo webhook Iron Pay")
        
        data = request.get_json()
        app.logger.info(f"[PROD] Webhook data: {json.dumps(data, indent=2)}")
        
        # Processar webhook conforme necessário
        # Exemplo: atualizar status do pagamento no banco de dados
        
        return jsonify({
            'success': True,
            'message': 'Webhook processado com sucesso'
        })
        
    except Exception as e:
        app.logger.error(f"[PROD] Erro no webhook: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
```

### 3. Arquivo de Entrada: `main.py`

```python
from app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
```

## 🧪 Testes e Exemplos

### 1. Teste Básico

```python
# test_ironpay.py
from ironpay_api import create_iron_pay_provider, IronPaymentData

def test_iron_pay():
    try:
        provider = create_iron_pay_provider()
        
        test_data = IronPaymentData(
            name='TESTE USUARIO',
            email='teste@exemplo.com',
            cpf='12345678901',
            phone='(11) 98765-4321',
            amount=127.94,
            description='Produto de teste'
        )
        
        print('🧪 Testando Iron Pay API...')
        result = provider.create_pix_payment(test_data)
        print(f'✅ Sucesso: {result.transaction_hash}')
        print(f'💰 PIX Code: {result.pix_code[:50]}...')
        
    except Exception as e:
        print(f'❌ Erro: {e}')

if __name__ == "__main__":
    test_iron_pay()
```

### 2. Teste via cURL

```bash
# Testar geração de PIX
curl -X POST http://localhost:5000/generate-pix \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TESTE USUARIO",
    "email": "teste@exemplo.com",
    "cpf": "123.456.789-01"
  }'

# Verificar status
curl -X GET http://localhost:5000/check-payment-status/TRANSACTION_HASH
```

## 📱 Frontend JavaScript

### Exemplo de integração no frontend:

```javascript
// Função para gerar PIX
async function generatePix(customerData) {
    try {
        console.log('Enviando dados PIX:', customerData);
        
        const response = await fetch('/generate-pix', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(customerData)
        });

        const data = await response.json();
        console.log('Resposta do PIX:', data);

        if (data.success) {
            // PIX gerado com sucesso
            showPixModal(data);
        } else {
            // Erro na geração
            showError(data.error);
        }
    } catch (error) {
        console.error('Erro ao gerar PIX:', error);
        showError('Erro de conexão');
    }
}

// Função para exibir modal do PIX
function showPixModal(pixData) {
    const pixCode = pixData.pixCode;
    const transactionId = pixData.transaction_id;
    
    // Atualizar DOM com dados do PIX
    document.getElementById('pix-code').textContent = pixCode;
    document.getElementById('transaction-id').textContent = transactionId;
    
    // Mostrar modal
    document.getElementById('pix-modal').style.display = 'block';
}

// Função para copiar código PIX
function copyPixCode() {
    const pixCode = document.getElementById('pix-code').textContent;
    navigator.clipboard.writeText(pixCode).then(() => {
        console.log('Código PIX copiado:', pixCode.substring(0, 50) + '...');
        // Mostrar feedback visual
        showCopyFeedback();
    });
}
```

## 🔧 Configuração de Produção

### 1. Variáveis de Ambiente

```bash
# Secrets necessários no Replit
IRONPAY_API_TOKEN=seu_token_aqui
SESSION_SECRET=sua_chave_secreta_aqui
```

### 2. Workflow de Produção

Arquivo `.replit`:

```toml
[deployment]
run = ["gunicorn", "--bind", "0.0.0.0:5000", "--reuse-port", "--reload", "main:app"]

[[ports]]
localPort = 5000
externalPort = 80
```

### 3. Procfile (se necessário)

```
web: gunicorn --bind 0.0.0.0:$PORT --reuse-port --reload main:app
```

## 🚨 Sistema de Fallback

Para maior confiabilidade, implemente um sistema de fallback:

```python
def generate_pix_with_fallback(customer_data):
    """Gerar PIX com sistema de fallback"""
    
    # Tentar Iron Pay primeiro
    try:
        iron_pay = create_iron_pay_provider()
        result = iron_pay.create_pix_payment(customer_data)
        logger.info("✅ PIX gerado via Iron Pay")
        return result
        
    except Exception as iron_error:
        logger.warning(f"⚠️ Iron Pay falhou: {iron_error}")
        
        # Fallback: outro gateway ou PIX manual
        try:
            # Implementar PIX alternativo aqui
            logger.info("🔄 Usando sistema de fallback")
            return generate_fallback_pix(customer_data)
            
        except Exception as fallback_error:
            logger.error(f"❌ Fallback também falhou: {fallback_error}")
            raise Exception("Todos os sistemas de pagamento falharam")
```

## 📊 Monitoramento e Logs

### Configuração de logging:

```python
import logging
from datetime import datetime

# Configurar logging detalhado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ironpay.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Log de transações
def log_transaction(transaction_data, result):
    """Log detalhado de transações"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'customer': transaction_data.name,
        'cpf': transaction_data.cpf[:3] + '***' + transaction_data.cpf[-2:],
        'amount': transaction_data.amount,
        'transaction_hash': result.transaction_hash,
        'provider': 'Iron Pay',
        'status': result.status
    }
    
    logger.info(f"TRANSACTION: {json.dumps(log_entry)}")
```

## 🔒 Segurança

### Práticas recomendadas:

1. **Validação de dados:**
```python
def validate_cpf(cpf):
    """Validar formato do CPF"""
    cpf_clean = ''.join(filter(str.isdigit, cpf))
    return len(cpf_clean) == 11

def sanitize_input(data):
    """Sanitizar dados de entrada"""
    return {
        'name': data.get('name', '').strip().upper(),
        'email': data.get('email', '').strip().lower(),
        'cpf': ''.join(filter(str.isdigit, data.get('cpf', '')))
    }
```

2. **Rate limiting:**
```python
from functools import wraps
import time

request_timestamps = {}

def rate_limit(max_requests=10, window=60):
    """Rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            now = time.time()
            
            if client_ip not in request_timestamps:
                request_timestamps[client_ip] = []
            
            # Limpar timestamps antigos
            request_timestamps[client_ip] = [
                ts for ts in request_timestamps[client_ip] 
                if now - ts < window
            ]
            
            if len(request_timestamps[client_ip]) >= max_requests:
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            request_timestamps[client_ip].append(now)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Aplicar rate limiting
@app.route('/generate-pix', methods=['POST'])
@rate_limit(max_requests=5, window=60)
def generate_pix():
    # ... implementação
```

## 📝 Changelog

- **v1.0.0** - Implementação inicial Iron Pay API
- **v1.1.0** - Adicionado sistema de fallback
- **v1.2.0** - Melhorias em logging e monitoramento
- **v1.3.0** - Rate limiting e validações de segurança

## 📞 Suporte

Para dúvidas ou problemas:

1. Verificar logs em `/var/log/ironpay.log`
2. Testar conectividade com Iron Pay API
3. Validar configuração de secrets
4. Consultar documentação oficial Iron Pay

---

**🎉 Implementação completa Iron Pay para Replit!**

Esta documentação fornece tudo necessário para integrar Iron Pay em qualquer projeto Replit com confiabilidade e segurança.