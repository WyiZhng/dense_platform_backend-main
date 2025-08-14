#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSL证书生成脚本
用于生成自签名SSL证书，供开发环境使用
使用Python内置的cryptography库生成证书，无需外部OpenSSL工具
"""

import os
import sys
import ipaddress
from pathlib import Path
from datetime import datetime, timedelta, timezone

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    print("❌ 缺少cryptography库")
    print("请安装: pip install cryptography")
    sys.exit(1)

def generate_ssl_certificate():
    """
    使用Python cryptography库生成自签名SSL证书
    生成的文件:
    - server.key: 私钥文件
    - server.crt: 证书文件
    """
    
    # 获取当前脚本所在目录
    current_dir = Path(__file__).parent
    
    # 证书文件路径
    key_file = current_dir / "server.key"
    cert_file = current_dir / "server.crt"
    
    print("正在生成SSL证书...")
    
    try:
        # 1. 生成私钥
        print("1. 生成RSA私钥...")
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # 2. 创建证书主题信息
        print("2. 创建证书主题信息...")
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Beijing"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Beijing"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Development"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "IT"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        
        # 3. 生成证书
        print("3. 生成自签名证书...")
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.now(timezone.utc)
        ).not_valid_after(
            # 证书有效期365天
            datetime.now(timezone.utc) + timedelta(days=365)
        ).add_extension(
            # 添加Subject Alternative Name扩展，支持localhost和127.0.0.1
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # 4. 保存私钥文件
        print("4. 保存私钥文件...")
        with open(key_file, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        # 5. 保存证书文件
        print("5. 保存证书文件...")
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        print(f"✅ SSL证书生成成功!")
        print(f"   私钥文件: {key_file}")
        print(f"   证书文件: {cert_file}")
        print(f"   证书有效期: 365天")
        print(f"   支持域名: localhost, 127.0.0.1")
        print("\n⚠️  注意: 这是自签名证书，仅用于开发环境")
        print("   浏览器会显示安全警告，这是正常的")
        
        return True
        
    except Exception as e:
        print(f"❌ 生成证书失败: {e}")
        return False

def check_certificates_exist():
    """
    检查证书文件是否已存在
    """
    current_dir = Path(__file__).parent
    key_file = current_dir / "server.key"
    cert_file = current_dir / "server.crt"
    
    return key_file.exists() and cert_file.exists()

if __name__ == "__main__":
    print("=== SSL证书生成工具 ===")
    
    # 检查证书是否已存在
    if check_certificates_exist():
        print("✅ SSL证书文件已存在")
        response = input("是否要重新生成? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("跳过证书生成")
            sys.exit(0)
    
    # 生成证书
    success = generate_ssl_certificate()
    
    if success:
        print("\n🚀 现在可以使用HTTPS启动服务器了!")
        print("   运行: python main.py")
    else:
        print("\n❌ 证书生成失败，请检查OpenSSL安装")
        sys.exit(1)