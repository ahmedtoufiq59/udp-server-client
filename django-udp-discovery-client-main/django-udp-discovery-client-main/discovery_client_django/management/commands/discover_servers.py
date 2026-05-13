"""
Django management command to discover django-udp-discovery servers.

Usage:
    python manage.py discover_servers
    python manage.py discover_servers --timeout 10.0
    python manage.py discover_servers --port 9999
"""
from django.core.management.base import BaseCommand
from django.core.management import CommandError
from discovery_client import discover, ClientConfig, DiscoveryResult, load_config
from discovery_client.network.socket import (
    detect_segmented_network,
    format_segmented_network_warning,
)
from discovery_client.network.interfaces import select_interfaces
from typing import List


class Command(BaseCommand):
    """Management command to discover django-udp-discovery servers."""
    
    help = 'Discover django-udp-discovery servers on the local network'
    
    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            '--timeout',
            type=float,
            default=5.0,
            help='Discovery timeout in seconds (default: 5.0)',
        )
        parser.add_argument(
            '--port',
            type=int,
            default=9999,
            help='Discovery port (default: 9999)',
        )
        parser.add_argument(
            '--message',
            type=str,
            default='DISCOVER_SERVER',
            help='Discovery message (default: DISCOVER_SERVER)',
        )
        parser.add_argument(
            '--response-prefix',
            type=str,
            default='SERVER_IP:',
            help='Expected response prefix (default: SERVER_IP:)',
        )
        parser.add_argument(
            '--interfaces-whitelist',
            type=str,
            help='Comma-separated list of interface names to whitelist',
        )
        parser.add_argument(
            '--interfaces-blacklist',
            type=str,
            help='Comma-separated list of interface names to blacklist',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )
        parser.add_argument(
            '--encryption',
            action='store_true',
            help=(
                'Use Fernet-encrypted discovery (must match server '
                'DISCOVERY_ENCRYPTION_ENABLED). Secret: DISCOVERY_CLIENT_SECRET_KEY '
                'or DISCOVERY_SECRET_KEY env var.'
            ),
        )
    
    def handle(self, *args, **options):
        """Execute the discovery command."""
        config_kwargs = {
            'timeout': options['timeout'],
            'discovery_port': options['port'],
            'discovery_message': options['message'].encode('utf-8'),
            'response_prefix': options['response_prefix'].encode('utf-8'),
        }

        if options['encryption']:
            config_kwargs['encryption_enabled'] = True

        # Handle interface filters
        if options['interfaces_whitelist']:
            config_kwargs['interfaces_whitelist'] = [
                name.strip() for name in options['interfaces_whitelist'].split(',')
            ]

        if options['interfaces_blacklist']:
            config_kwargs['interfaces_blacklist'] = [
                name.strip() for name in options['interfaces_blacklist'].split(',')
            ]

        try:
            config = load_config(**config_kwargs)
        except ValueError as e:
            raise CommandError(f"Invalid configuration: {e}")

        # Perform discovery
        if options['verbose']:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Starting discovery (timeout: {config.timeout}s, port: {config.discovery_port})...'
                )
            )
        
        try:
            servers = discover(config=config)
        except Exception as e:
            raise CommandError(f"Discovery failed: {e}")
        
        # Display results
        if not servers:
            self.stdout.write(
                self.style.WARNING('No servers found on the network.')
            )
            self.stdout.write(
                'Make sure django-udp-discovery servers are running and accessible.'
            )
            # Print segmented network diagnostic exactly once, after all interfaces scanned
            try:
                interfaces = select_interfaces(config)
                segmented_info = detect_segmented_network(interfaces) if interfaces else None
                if segmented_info:
                    self.stdout.write(
                        format_segmented_network_warning(segmented_info, width=40)
                    )
            except ImportError:
                pass
            return
        
        # Print table of discovered servers
        self._print_results_table(servers, verbose=options['verbose'])
    
    def _print_results_table(self, servers: List[DiscoveryResult], verbose: bool = False):
        """
        Print a formatted table of discovered servers.
        
        Args:
            servers: List of DiscoveryResult objects
            verbose: If True, include raw response in output
        """
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Found {len(servers)} server(s):'))
        self.stdout.write('')
        
        # Table header
        if verbose:
            header = f"{'IP Address':<18} {'Port':<8} {'Raw Response':<50}"
        else:
            header = f"{'IP Address':<18} {'Port':<8} {'URL':<30}"
        
        self.stdout.write(self.style.SUCCESS(header))
        self.stdout.write(self.style.SUCCESS('-' * len(header)))
        
        # Table rows
        for server in servers:
            ip = server.ip
            port = str(server.port)
            
            if verbose:
                raw_response = server.raw_response.decode('utf-8', errors='replace')[:50]
                row = f"{ip:<18} {port:<8} {raw_response:<50}"
            else:
                url = f"http://{ip}:{port}"
                row = f"{ip:<18} {port:<8} {url:<30}"
            
            self.stdout.write(row)
            
            # Show extra metadata if available
            if verbose and server.extra:
                for key, value in server.extra.items():
                    self.stdout.write(f"  {key}: {value}")
        
        self.stdout.write('')
