## Architecture

The WireGuard Bridge uses a fully Python-controlled architecture which is divided into 5 phases:

1. **Phase 1**: Infrastructure setup
2. **Phase 2**: OpenVPN client setup and configuration
3. **Phase 3**: WireGuard config generation
4. **Phase 4**: WireGuard server setup
5. **Phase 5**: Health checking and process monitoring

## How it works

Phase 1:

- Enable IP forwarding
- Find OpenVPN config

Phase 2:

- Start OpenVPN client
- Wait for tunnel to be established (tun interface is up)

Phase 3:

- Generate or restore WireGuard server keys
- Generate or restore WireGuard clients keys
- Generate or restore WireGuard server config

Phase 4:

- Start WireGuard server
- Wait for WireGuard server to be ready
- Ready to use

Phase 5(passive):

- Monitor OpenVPN client and WireGuard server processes and restart them if they crash
- Manage restart on new clients addition in runtime
