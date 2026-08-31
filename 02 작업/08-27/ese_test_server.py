import asyncio
import logging
from pathlib import Path

from asyncua import Server, ua
from asyncua.crypto.cert_gen import setup_self_signed_certificate

logging.basicConfig(level=logging.INFO)
logging.getLogger("asyncua.server.uaprocessor").setLevel(logging.DEBUG)
from cryptography.x509.oid import ExtendedKeyUsageOID


async def main():
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://100.115.39.43:4846/freeopcua/server/")

    app_uri = "urn:freeopcua:python:server"
    cert_dir = Path(__file__).parent / "certs"
    cert_dir.mkdir(exist_ok=True)
    await setup_self_signed_certificate(
        key_file=cert_dir / "server_key.pem",
        cert_file=cert_dir / "server_cert.der",
        app_uri=app_uri,
        host_name="localhost",
        cert_use=[ExtendedKeyUsageOID.SERVER_AUTH],
        subject_attrs={
            "countryName": "KR",
            "stateOrProvinceName": "Seoul",
            "localityName": "Seoul",
            "organizationName": "TestServer",
            "commonName": "ese_test_server",
        },
    )
    await server.load_certificate(str(cert_dir / "server_cert.der"))
    await server.load_private_key(str(cert_dir / "server_key.pem"))

    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])

    uri = "http://example.org/myserver"
    idx = await server.register_namespace(uri)

    async with server:
        objects = server.get_objects_node()
        plc_obj = await objects.add_object(idx, "PLC")

        temp_var = await plc_obj.add_variable(idx, "Temperature", 25.0)
        await temp_var.set_writable()

        busy_var = await plc_obj.add_variable(
            idx, "Busy", ua.Variant(False, ua.VariantType.Boolean)
        )
        await busy_var.set_writable()

        count_var = await plc_obj.add_variable(
            idx, "Count", ua.Variant(0, ua.VariantType.Int32)
        )
        await count_var.set_writable()

        msg_var = await plc_obj.add_variable(idx, "Message", "hello")
        await msg_var.set_writable()

        print("서버 실행 중... (Ctrl+C로 종료)")
        print("Endpoint: opc.tcp://100.115.39.43:4846/freeopcua/server/ (Tailscale)")

        toggle = False
        count = 0
        while True:
            await asyncio.sleep(3)
            toggle = not toggle
            count += 1
            await busy_var.write_value(ua.Variant(toggle, ua.VariantType.Boolean))
            await count_var.write_value(ua.Variant(count, ua.VariantType.Int32))
            print(f"Busy -> {toggle}, Count -> {count}")


if __name__ == "__main__":
    asyncio.run(main())
