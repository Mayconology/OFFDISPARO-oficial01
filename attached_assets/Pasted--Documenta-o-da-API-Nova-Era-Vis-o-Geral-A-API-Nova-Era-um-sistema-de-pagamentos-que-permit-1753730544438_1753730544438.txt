# Documentação da API Nova Era

## Visão Geral

A API Nova Era é um sistema de pagamentos que permite processar transações via PIX de forma segura e eficiente. Esta documentação fornece todas as informações necessárias para integrar a API em seus projetos.

## Base URL

```
https://api.novaera-pagamentos.com/api/v1
```

## Autenticação

A API utiliza autenticação Basic Auth com chaves de API. Você precisa das seguintes credenciais:

- **Secret Key**: `sk_tpiM8TWOjQsHKZ6Fnhm2u8JgR9jWs5A8r1Lw4SqhnyfmBZ9o`
- **Public Key**: `pk_h8op2k72EbiEhVFvdio8gXd8Kc-IbN_SVXrjJxx4eyAGlor0`

### Gerando o Token de Autenticação

```python
import base64

def get_payment_token():
    secret = "sk_tpiM8TWOjQsHKZ6Fnhm2u8JgR9jWs5A8r1Lw4SqhnyfmBZ9o"
    public_key = "pk_h8op2k72EbiEhVFvdio8gXd8Kc-IbN_SVXrjJxx4eyAGlor0"
    
    credentials = f"{secret}:{public_key}"
    token = base64.b64encode(credentials.encode()).decode()
    
    return f"Basic {token}"
```

```javascript
function getPaymentToken() {
    const secret = "sk_tpiM8TWOjQsHKZ6Fnhm2u8JgR9jWs5A8r1Lw4SqhnyfmBZ9o";
    const publicKey = "pk_h8op2k72EbiEhVFvdio8gXd8Kc-IbN_SVXrjJxx4eyAGlor0";
    
    const token = btoa(unescape(encodeURIComponent(`${secret}:${publicKey}`)));
    
    return "Basic " + token;
}
```

## Endpoints

### 1. Criar Transação PIX

Cria uma nova transação PIX para pagamento.

**Endpoint:** `POST /transactions`

**Headers:**
```
Content-Type: application/json
Authorization: Basic {token}
```

**Body:**
```json
{
    "customer": {
        "name": "João Silva",
        "email": "joao@email.com",
        "phone": "(11) 99999-9999",
        "document": {
            "number": "12345678901",
            "type": "cpf"
        }
    },
    "items": [
        {
            "tangible": false,
            "quantity": 1,
            "unitPrice": 8740,
            "title": "Inscrição digital"
        }
    ],
    "postbackUrl": "https://seu-webhook.com/callback",
    "amount": 8740,
    "paymentMethod": "pix"
}
```

**Resposta de Sucesso (200):**
```json
{
    "success": true,
    "data": {
        "id": "txn_abc123def456",
        "status": "waiting_payment",
        "amount": 8740,
        "customer": {
            "name": "João Silva",
            "email": "joao@email.com",
            "phone": "(11) 99999-9999",
            "document": {
                "number": "12345678901",
                "type": "cpf"
            }
        },
        "pix": {
            "qrcode": "00020126580014br.gov.bcb.pix...",
            "expires_at": "2025-01-15T10:30:00Z"
        },
        "created_at": "2025-01-15T10:20:00Z"
    }
}
```

**Resposta de Erro (400):**
```json
{
    "success": false,
    "error": {
        "code": "INVALID_CPF",
        "message": "CPF inválido"
    }
}
```

### 2. Consultar Status da Transação

Consulta o status atual de uma transação.

**Endpoint:** `GET /transactions/{transaction_id}`

**Headers:**
```
Authorization: Basic {token}
```

**Resposta de Sucesso (200):**
```json
{
    "success": true,
    "data": {
        "id": "txn_abc123def456",
        "status": "paid",
        "amount": 8740,
        "customer": {
            "name": "João Silva",
            "email": "joao@email.com",
            "phone": "(11) 99999-9999",
            "document": {
                "number": "12345678901",
                "type": "cpf"
            }
        },
        "paid_at": "2025-01-15T10:25:00Z",
        "created_at": "2025-01-15T10:20:00Z"
    }
}
```

## Status das Transações

| Status | Descrição |
|--------|-----------|
| `waiting_payment` | Aguardando pagamento |
| `paid` | Pagamento confirmado |
| `expired` | Transação expirada |
| `cancelled` | Transação cancelada |
| `failed` | Falha no pagamento |

## Códigos de Erro

| Código | Descrição |
|--------|-----------|
| `INVALID_CPF` | CPF inválido |
| `INVALID_EMAIL` | Email inválido |
| `INVALID_PHONE` | Telefone inválido |
| `INSUFFICIENT_DATA` | Dados insuficientes |
| `TRANSACTION_NOT_FOUND` | Transação não encontrada |
| `EXPIRED_TRANSACTION` | Transação expirada |

## Exemplos de Implementação

### Python (usando requests)

```python
import requests
import json
import base64

class NovaEraAPI:
    def __init__(self):
        self.base_url = "https://api.novaera-pagamentos.com/api/v1"
        self.secret = "sk_tpiM8TWOjQsHKZ6Fnhm2u8JgR9jWs5A8r1Lw4SqhnyfmBZ9o"
        self.public_key = "pk_h8op2k72EbiEhVFvdio8gXd8Kc-IbN_SVXrjJxx4eyAGlor0"
    
    def get_auth_token(self):
        credentials = f"{self.secret}:{self.public_key}"
        token = base64.b64encode(credentials.encode()).decode()
        return f"Basic {token}"
    
    def create_transaction(self, customer_data, amount, items):
        url = f"{self.base_url}/transactions"
        
        payload = {
            "customer": customer_data,
            "items": items,
            "postbackUrl": "https://seu-webhook.com/callback",
            "amount": amount,
            "paymentMethod": "pix"
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.get_auth_token()
        }
        
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    
    def get_transaction_status(self, transaction_id):
        url = f"{self.base_url}/transactions/{transaction_id}"
        
        headers = {
            "Authorization": self.get_auth_token()
        }
        
        response = requests.get(url, headers=headers)
        return response.json()

# Exemplo de uso
api = NovaEraAPI()

customer = {
    "name": "João Silva",
    "email": "joao@email.com",
    "phone": "(11) 99999-9999",
    "document": {
        "number": "12345678901",
        "type": "cpf"
    }
}

items = [
    {
        "tangible": False,
        "quantity": 1,
        "unitPrice": 8740,
        "title": "Inscrição digital"
    }
]

# Criar transação
result = api.create_transaction(customer, 8740, items)
print(json.dumps(result, indent=2))

# Consultar status
if result.get("success"):
    transaction_id = result["data"]["id"]
    status = api.get_transaction_status(transaction_id)
    print(json.dumps(status, indent=2))
```

### HTML + JavaScript

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nova Era API - Exemplo</title>
</head>
<body>
    <h1>Pagamento PIX - Nova Era</h1>
    
    <form id="paymentForm">
        <div>
            <label>Nome:</label>
            <input type="text" id="name" required>
        </div>
        <div>
            <label>Email:</label>
            <input type="email" id="email" required>
        </div>
        <div>
            <label>Telefone:</label>
            <input type="tel" id="phone" required>
        </div>
        <div>
            <label>CPF:</label>
            <input type="text" id="cpf" required>
        </div>
        <div>
            <label>Valor (R$):</label>
            <input type="number" id="amount" step="0.01" required>
        </div>
        <button type="submit">Gerar PIX</button>
    </form>
    
    <div id="result" style="display: none;">
        <h2>QR Code PIX</h2>
        <div id="qrcode"></div>
        <p>Código PIX: <span id="pixCode"></span></p>
        <button onclick="copyPixCode()">Copiar Código</button>
    </div>

    <script>
        function getPaymentToken() {
            const secret = "sk_tpiM8TWOjQsHKZ6Fnhm2u8JgR9jWs5A8r1Lw4SqhnyfmBZ9o";
            const publicKey = "pk_h8op2k72EbiEhVFvdio8gXd8Kc-IbN_SVXrjJxx4eyAGlor0";
            
            const token = btoa(unescape(encodeURIComponent(`${secret}:${publicKey}`)));
            return "Basic " + token;
        }

        async function createTransaction(customerData, amount) {
            const response = await fetch("https://api.novaera-pagamentos.com/api/v1/transactions", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": getPaymentToken()
                },
                body: JSON.stringify({
                    customer: customerData,
                    items: [
                        {
                            tangible: false,
                            quantity: 1,
                            unitPrice: amount * 100,
                            title: "Pagamento"
                        }
                    ],
                    postbackUrl: "https://seu-webhook.com/callback",
                    amount: amount * 100,
                    paymentMethod: "pix"
                })
            });

            return await response.json();
        }

        async function checkTransactionStatus(transactionId) {
            const response = await fetch(`https://api.novaera-pagamentos.com/api/v1/transactions/${transactionId}`, {
                headers: {
                    "Authorization": getPaymentToken()
                }
            });

            return await response.json();
        }

        document.getElementById('paymentForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const customerData = {
                name: document.getElementById('name').value,
                email: document.getElementById('email').value,
                phone: document.getElementById('phone').value,
                document: {
                    number: document.getElementById('cpf').value.replace(/\D/g, ''),
                    type: "cpf"
                }
            };
            
            const amount = parseFloat(document.getElementById('amount').value);
            
            try {
                const result = await createTransaction(customerData, amount);
                
                if (result.success) {
                    document.getElementById('pixCode').textContent = result.data.pix.qrcode;
                    document.getElementById('result').style.display = 'block';
                    
                    // Monitorar status da transação
                    const transactionId = result.data.id;
                    const statusInterval = setInterval(async () => {
                        const status = await checkTransactionStatus(transactionId);
                        if (status.data.status === 'paid') {
                            alert('Pagamento confirmado!');
                            clearInterval(statusInterval);
                        }
                    }, 3000);
                } else {
                    alert('Erro: ' + result.error.message);
                }
            } catch (error) {
                alert('Erro na requisição: ' + error.message);
            }
        });

        function copyPixCode() {
            const pixCode = document.getElementById('pixCode').textContent;
            navigator.clipboard.writeText(pixCode).then(() => {
                alert('Código PIX copiado!');
            });
        }
    </script>
</body>
</html>
```

## Webhook (Postback)

A API Nova Era envia notificações sobre mudanças no status das transações através de webhooks.

### Estrutura do Webhook

**Método:** `POST`
**Content-Type:** `application/json`

**Payload:**
```json
{
    "event": "transaction.paid",
    "data": {
        "id": "txn_abc123def456",
        "status": "paid",
        "amount": 8740,
        "customer": {
            "name": "João Silva",
            "email": "joao@email.com",
            "phone": "(11) 99999-9999",
            "document": {
                "number": "12345678901",
                "type": "cpf"
            }
        },
        "paid_at": "2025-01-15T10:25:00Z",
        "created_at": "2025-01-15T10:20:00Z"
    }
}
```

### Eventos Disponíveis

- `transaction.created` - Transação criada
- `transaction.paid` - Pagamento confirmado
- `transaction.expired` - Transação expirada
- `transaction.cancelled` - Transação cancelada
- `transaction.failed` - Falha no pagamento

## Considerações de Segurança

1. **Nunca exponha suas chaves secretas** no frontend
2. **Use HTTPS** em todas as comunicações
3. **Valide os webhooks** verificando a origem
4. **Implemente timeout** nas requisições
5. **Trate erros adequadamente**

## Limites e Restrições

- **Rate Limit:** 100 requisições por minuto
- **Timeout:** 30 segundos por requisição
- **Valor mínimo:** R$ 0,01
- **Valor máximo:** R$ 50.000,00
- **Expiração PIX:** 10 minutos

## Suporte

Para dúvidas ou problemas com a API, entre em contato:

- **Email:** suporte@novaera-pagamentos.com
- **Documentação:** https://docs.novaera-pagamentos.com
- **Status da API:** https://status.novaera-pagamentos.com

## Changelog

### v1.0.0 (2025-01-15)
- Lançamento inicial da API
- Suporte a pagamentos PIX
- Sistema de webhooks
- Autenticação Basic Auth