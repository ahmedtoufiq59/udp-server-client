#!/usr/bin/env python3
"""
Sanity check script for django-udp-discovery-client.

Verifies that the installed package can perform UDP discovery on the local
network. Run after pip install (e.g. pip install django-udp-discovery-client[network]):

    python scripts/sanity_check.py

Or from the repo root when installed in editable mode:

    python scripts/sanity_check.py

Prints active interfaces with broadcast addresses, runs discovery, and shows
a table of discovered servers. If no servers are found on a segmented network
(large corporate subnet), prints a helpful explanation.
"""
from __future__ import print_function

import sys


def main():
    # Use the installed package (no path hacks)
    try:
        from discovery_client import load_config, discover
        from discovery_client.network.interfaces import get_interfaces, select_interfaces
        from discovery_client.network.socket import (
            detect_segmented_network,
            get_interface_broadcast,
            format_segmented_network_warning,
        )
    except ImportError as e:
        print("Error: Could not import discovery_client.", file=sys.stderr)
        print("Install the package first: pip install django-udp-discovery-client[network]", file=sys.stderr)
        print("Details:", e, file=sys.stderr)
        return 1

    config = load_config()

    # --- List active interfaces and broadcast addresses ---
    print("Network interfaces (used for discovery)")
    print("-" * 60)
    try:
        all_interfaces = get_interfaces()
        selected = select_interfaces(config)
    except ImportError as e:
        print("Warning: Could not enumerate interfaces (missing netifaces/ifaddr).")
        print("Install with: pip install django-udp-discovery-client[network]")
        print("Discovery will still be attempted but may fail or use limited interfaces.")
        all_interfaces = []
        selected = []

    selected_names = {s.name for s in selected}

    if not all_interfaces:
        print("No active IPv4 interfaces found.")
    else:
        for iface in all_interfaces:
            try:
                broadcast = get_interface_broadcast(iface)
            except ValueError:
                broadcast = "(unable to compute)"
            used = " [SELECTED]" if iface.name in selected_names else ""
            print("  {}  {} / {}  -> broadcast {} {}".format(
                iface.name, iface.ip, iface.netmask, broadcast, used
            ))

    if selected:
        print("\nBroadcast addresses used for discovery:")
        for iface in selected:
            try:
                broadcast = get_interface_broadcast(iface)
                print("  {} -> {}:{}".format(iface.name, broadcast, config.discovery_port))
            except ValueError:
                print("  {} -> (skipped, invalid broadcast)".format(iface.name))

    # --- Run discovery ---
    print("\nRunning discovery (timeout={}s, port={})...".format(config.timeout, config.discovery_port))
    import logging
    logging.getLogger("django_udp_discovery_client").setLevel(logging.ERROR)
    results = discover(config=config)

    # --- Results table ---
    print("\nDiscovery results")
    print("-" * 60)
    if not results:
        print("  No servers found.")
        print("  Tip: Ensure django-udp-discovery servers are running and listening on port {}.".format(config.discovery_port))
        # Segmented network diagnostic: exactly once at end, only when no discovery results
        if selected:
            segmented_info = detect_segmented_network(selected)
            if segmented_info:
                print()
                print(format_segmented_network_warning(segmented_info, width=40))
        return 0

    # Format: IP, Port, Response (truncate long response)
    col_ip = 18
    col_port = 8
    col_response = 44
    header = "{:<{}} {:<{}} {:<{}}".format("IP", col_ip, "Port", col_port, "Response", col_response)
    print(header)
    print("-" * len(header))
    for r in results:
        resp_str = r.raw_response.decode("utf-8", errors="replace").strip()
        if len(resp_str) > col_response:
            resp_str = resp_str[: col_response - 3] + "..."
        print("{:<{}} {:<{}} {:<{}}".format(r.ip, col_ip, r.port, col_port, resp_str, col_response))
    print("\nTotal: {} server(s)".format(len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
