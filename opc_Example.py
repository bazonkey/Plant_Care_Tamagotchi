import asyncio
from asyncua import Client, ua
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256

# SERVER_URL = "opc.tcp://100.90.187.71:4840/myopcua/server"
SERVER_URL = "opc.tcp://100.100.12.80:4840/myopcua/server"

CLIENT_CERT = "pki/own/certs/client_cert.der"
CLIENT_KEY = "pki/own/private/client_key.pem"
# SERVER_CERT = "pki/trusted/certs/server_cert.der"


async def opc_read(client, var_to_read):
    failed = 0
    try:
        await client.connect()
        uri = "http://myopcua.server"
        idx = await client.get_namespace_index(uri)
        

        var = client.get_node(f"ns={idx};s={var_to_read}")
        val = await var.read_value()
        print(val)


    except Exception as e:
        failed = 1
        print("CONNECT FAILED:", type(e).__name__, e)
    finally:
        try:
            await client.disconnect()
            print("Disconnected")
        except Exception:
            print("Disconnect errored")
            pass
    if not failed:
        return val
    else:
        return None
    
        













async def main():
    # Create the Client
    client = Client(SERVER_URL)
    client.application_uri = "urn:trevor:opcua:client"
    await client.set_security(
        SecurityPolicyBasic256Sha256,
        certificate = CLIENT_CERT,
        private_key=CLIENT_KEY,
        # server_certificate=SERVER_CERT,
    )


    # Example read
    water = await opc_read(client, "Water")

    

asyncio.run(main())


