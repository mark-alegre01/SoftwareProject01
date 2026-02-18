/*
  CA Certificate for HTTPS verification on ESP32
  
  This certificate is used to verify the Django server's SSL certificate.
  Generated automatically from: ssl_certs/server.crt
  
  To regenerate this file, run:
    python extract_ca_cert.py
*/

#ifndef CA_CERT_H
#define CA_CERT_H

// Self-signed certificate for Django RFID server (localhost)
// Valid for development and local network access
const char* ca_cert = R"(-----BEGIN CERTIFICATE-----
MIIDYzCCAksCAgPoMA0GCSqGSIb3DQEBCwUAMHcxCzAJBgNVBAYTAlVTMQ4wDAYD
VQQIDAVMb2NhbDEOMAwGA1UEBwwFTG9jYWwxHjAcBgNVBAoMFVJGSUQgQm9ycm93
aW5nIFN5c3RlbTEUMBIGA1UECwwLRGV2ZWxvcG1lbnQxEjAQBgNVBAMMCWxvY2Fs
aG9zdDAeFw0yNTExMTIxNzU5MjhaFw0yNjExMTIxNzU5MjhaMHcxCzAJBgNVBAYT
AlVTMQ4wDAYDVQQIDAVMb2NhbDEOMAwGA1UEBwwFTG9jYWwxHjAcBgNVBAoMFVJG
SUQgQm9ycm93aW5nIFN5c3RlbTEUMBIGA1UECwwLRGV2ZWxvcG1lbnQxEjAQBgNV
BAMMCWxvY2FsaG9zdDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBALhp
jBP9B2kJfHzHRWyumWireyI9vvDU94Mnq3syu0kyFm3uYyvfeCGZoO1zmflRBJsK
AH1cAK70KtlubYnqjXfKw2SzJLM/dkHxlzsyYUqsbvX/HEexgaVlx44HEUXxF2lA
H3EmzhofiJbHoXQ7QGl243uGB9iMMxBE32Jh+V1FczVVg2RZTlc3OUJ2i30A1PUA
Hn7QQnMKj/6u31H3Clop5O8xS7vAOORYYHEwArd8VHBfJnfYlIfcUigaWH60BaVN
GDNkr9WXgPM+tsUjOlDzVp+csTAuOc/4+/fVJu+bPegCs769ONL+MR3RgALs8s2y
tvy4+haDcPI+obigr8ECAwEAATANBgkqhkiG9w0BAQsFAAOCAQEAWyMIzCx8Ixpr
+fXe+0+Vc4cV3gzfF7o8Nyy/u/K0uI+DLgOVM/4OYoE/bQbX/jhuJ2IAT9a6MGFx
H52eP6iycd9SpEOWS12fx/iSDIUG8QNhWMedhdm+hTE9fTpUb7V5G/nGABWCcNTr
2sI8qisVMBa6Y+/wkUkzBeePpxEiGZ4BsAlWt2afkyLwdaJgBhGokVg4l1Lkmjfd
wuSMHBE++1Fy8a7DZd3NjZM83bhFyMX8AO3/3gb30K1dbT2lfNyYMa0ZgnhgSeun
SbTV3OjOh1kXv3YmVt84S9qTGwfQSixb69zOHUqD8p52LZ+GKq5YCm4YSIh9ny1V
U+Fcl1OgJw==
-----END CERTIFICATE-----
)";

#endif // CA_CERT_H
