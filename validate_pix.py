#!/usr/bin/env python3
"""
Script para validar código PIX gerado pela Nova Era API
"""

import re
import binascii

def validate_pix_code(pix_code: str) -> dict:
    """
    Valida estrutura do código PIX segundo padrão EMV/BR Code
    
    Args:
        pix_code: Código PIX para validar
        
    Returns:
        Dict com resultado da validação
    """
    if not pix_code or not isinstance(pix_code, str):
        return {"valid": False, "error": "Código PIX vazio ou inválido"}
    
    # Remover espaços e quebras de linha
    pix_code = pix_code.strip().replace(' ', '').replace('\n', '')
    
    # Verificar se contém apenas caracteres válidos (alfanuméricos, pontos, hífens, barras, asteriscos)
    if not re.match(r'^[0-9A-Za-z.\-/*]+$', pix_code):
        return {"valid": False, "error": f"Código PIX contém caracteres inválidos. Encontrados: {set(pix_code)}"}
    
    # Verificar comprimento mínimo e máximo
    if len(pix_code) < 50:
        return {"valid": False, "error": f"Código PIX muito curto: {len(pix_code)} caracteres"}
    
    if len(pix_code) > 512:
        return {"valid": False, "error": f"Código PIX muito longo: {len(pix_code)} caracteres"}
    
    # Verificar se inicia com "0002" (Payload Format Indicator)
    if not pix_code.startswith("0002"):
        return {"valid": False, "error": "Código PIX deve começar com '0002'"}
    
    # Verificar se termina com CRC16 (4 dígitos hexadecimais)
    if len(pix_code) < 4 or not re.match(r'^[0-9A-F]{4}$', pix_code[-4:]):
        return {"valid": False, "error": "CRC16 inválido no final do código"}
    
    # Verificar estrutura EMV básica
    try:
        result = parse_emv_structure(pix_code)
        return {"valid": True, **result}
    except Exception as e:
        return {"valid": False, "error": f"Erro na estrutura EMV: {str(e)}"}

def parse_emv_structure(pix_code: str) -> dict:
    """
    Analisa estrutura EMV do código PIX
    """
    pos = 0
    fields = {}
    
    while pos < len(pix_code) - 4:  # -4 para o CRC16 no final
        if pos + 4 > len(pix_code):
            break
            
        # Ler tag (2 dígitos)
        tag = pix_code[pos:pos+2]
        pos += 2
        
        # Ler tamanho (2 dígitos)
        if pos + 2 > len(pix_code):
            break
        try:
            length = int(pix_code[pos:pos+2])
        except ValueError:
            # Se não conseguir converter, pode ser parte dos dados
            break
        pos += 2
        
        # Ler valor
        if pos + length > len(pix_code):
            break
        value = pix_code[pos:pos+length]
        pos += length
        
        fields[tag] = {"length": length, "value": value}
    
    # Verificar campos obrigatórios
    required_fields = ["00", "01", "26", "52", "53", "58", "59", "60"]
    missing_fields = [field for field in required_fields if field not in fields]
    
    if missing_fields:
        raise ValueError(f"Campos obrigatórios ausentes: {missing_fields}")
    
    return {
        "fields_count": len(fields),
        "payload_format": fields.get("00", {}).get("value", ""),
        "point_of_initiation": fields.get("01", {}).get("value", ""),
        "merchant_category": fields.get("52", {}).get("value", ""),
        "currency": fields.get("53", {}).get("value", ""),
        "country_code": fields.get("58", {}).get("value", ""),
        "merchant_name": fields.get("59", {}).get("value", ""),
        "merchant_city": fields.get("60", {}).get("value", ""),
        "amount": fields.get("54", {}).get("value", "N/A"),
        "all_fields": list(fields.keys())
    }

def check_crc16(pix_code: str) -> bool:
    """
    Verifica CRC16 do código PIX
    """
    try:
        # Separar código e CRC
        code_without_crc = pix_code[:-4]
        provided_crc = pix_code[-4:]
        
        # Calcular CRC16 CCITT
        calculated_crc = calculate_crc16_ccitt(code_without_crc + "6304")
        
        return provided_crc.upper() == calculated_crc.upper()
    except:
        return False

def calculate_crc16_ccitt(data: str) -> str:
    """
    Calcula CRC16 CCITT para validação PIX
    """
    data_bytes = data.encode('ascii')
    crc = 0xFFFF
    
    for byte in data_bytes:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    
    return f"{crc:04X}"

if __name__ == "__main__":
    # Código PIX do log da Nova Era
    test_pix_code = "00020101021226880014br.gov.bcb.pix2566qrcode.microcashif.com.br/pix/971f24d3-c3f9-48c3-96c0-65be7569fea35204000053039865802BR5924PAG INTERMEDIACOES DE VE6015SAO BERNARDO DO62070503***6304256A"
    
    print("=== VALIDAÇÃO DO CÓDIGO PIX NOVA ERA ===")
    print(f"Código: {test_pix_code[:50]}...")
    print(f"Tamanho: {len(test_pix_code)} caracteres")
    print()
    
    # Analisar caracteres únicos no código
    unique_chars = set(test_pix_code)
    print(f"Caracteres únicos encontrados: {''.join(sorted(unique_chars))}")
    print()
    
    result = validate_pix_code(test_pix_code)
    
    print("RESULTADO DA VALIDAÇÃO:")
    print(f"✅ Válido: {result['valid']}")
    
    if result['valid']:
        print(f"📊 Campos encontrados: {result['fields_count']}")
        print(f"🏦 Nome do recebedor: {result['merchant_name']}")
        print(f"🏙️ Cidade: {result['merchant_city']}")
        print(f"🌍 País: {result['country_code']}")
        print(f"💰 Valor: {result['amount']}")
        print(f"🔢 Moeda: {result['currency']}")
        print(f"📋 Todos os campos: {result['all_fields']}")
        
        # Verificar CRC16
        crc_valid = check_crc16(test_pix_code)
        print(f"🔒 CRC16 válido: {crc_valid}")
        
    else:
        print(f"❌ Erro: {result['error']}")
    
    print("\n" + "="*50)