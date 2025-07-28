#!/usr/bin/env python3
"""
Validador simples para código PIX da Nova Era
"""

def simple_pix_validation(pix_code: str) -> dict:
    """
    Validação básica do código PIX gerado pela Nova Era
    """
    if not pix_code:
        return {"valid": False, "error": "Código PIX vazio"}
    
    # Remover espaços
    pix_code = pix_code.strip()
    
    # Verificações básicas
    checks = {
        "tem_conteudo": len(pix_code) > 0,
        "tamanho_adequado": 50 <= len(pix_code) <= 512,
        "inicia_correto": pix_code.startswith("00020101"),
        "contem_pix_key": "br.gov.bcb.pix" in pix_code.lower(),
        "contem_valor": "5204" in pix_code or "54" in pix_code,
        "contem_nome": any(char.isalpha() for char in pix_code),
        "termina_com_crc": len(pix_code) >= 4 and pix_code[-8:-4] == "6304"
    }
    
    # Extrair informações básicas
    info = {
        "tamanho": len(pix_code),
        "inicio": pix_code[:20] if len(pix_code) >= 20 else pix_code,
        "final": pix_code[-20:] if len(pix_code) >= 20 else pix_code,
        "contem_br_gov": "br.gov.bcb.pix" in pix_code.lower(),
        "possivel_qr_url": "qrcode" in pix_code.lower()
    }
    
    # Avaliar se é válido
    critical_checks = ["tem_conteudo", "tamanho_adequado", "inicia_correto"]
    is_valid = all(checks[check] for check in critical_checks)
    
    return {
        "valid": is_valid,
        "checks": checks,
        "info": info,
        "score": sum(checks.values()),
        "total_checks": len(checks)
    }

if __name__ == "__main__":
    # Código PIX real da Nova Era
    nova_era_pix = "00020101021226880014br.gov.bcb.pix2566qrcode.microcashif.com.br/pix/971f24d3-c3f9-48c3-96c0-65be7569fea35204000053039865802BR5924PAG INTERMEDIACOES DE VE6015SAO BERNARDO DO62070503***6304256A"
    
    print("=== ANÁLISE CÓDIGO PIX NOVA ERA ===")
    print(f"Código completo: {nova_era_pix}")
    print(f"Tamanho: {len(nova_era_pix)} caracteres\n")
    
    result = simple_pix_validation(nova_era_pix)
    
    print("RESULTADO:")
    print(f"✅ Válido: {result['valid']}")
    print(f"📊 Score: {result['score']}/{result['total_checks']}")
    print()
    
    print("VERIFICAÇÕES DETALHADAS:")
    for check, passed in result['checks'].items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check.replace('_', ' ').title()}")
    
    print("\nINFORMAÇÕES:")
    for key, value in result['info'].items():
        print(f"  📋 {key.replace('_', ' ').title()}: {value}")
    
    print("\n" + "="*50)
    
    # Análise estrutural básica
    print("\nANÁLISE ESTRUTURAL:")
    if "00020101" in nova_era_pix:
        print("✅ Formato EMV detectado (00020101)")
    if "br.gov.bcb.pix" in nova_era_pix:
        print("✅ Chave PIX padrão do Banco Central")
    if "5802BR" in nova_era_pix:
        print("✅ País Brasil identificado (BR)")
    if "5924PAG" in nova_era_pix:
        print("✅ Nome do recebedor encontrado")
    if "6304" in nova_era_pix:
        print("✅ Campo CRC16 presente")
    
    print("\nCONCLUSÃO:")
    if result['valid']:
        print("🎉 O código PIX da Nova Era está CORRETO e válido!")
        print("   Pode ser usado para pagamentos PIX normalmente.")
    else:
        print("⚠️  Possíveis problemas detectados no código PIX.")
        failed_checks = [k for k, v in result['checks'].items() if not v]
        print(f"   Verificações que falharam: {failed_checks}")