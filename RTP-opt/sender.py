import argparse
import socket
import sys
import time

from utils import PacketHeader, compute_checksum

def sender(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0.05)
    message = sys.stdin.buffer.read()

    MAX_CHUNK = 1472 - 16
    chunks = [message[i:i+MAX_CHUNK] for i in range(0, len(message), MAX_CHUNK)]

    packets = {}
    timers = {}  # maintain per-packet send times
    acked = {}   # mark individual ACKs

    start_pkt = PacketHeader(type=0, seq_num=0, length=0)
    start_pkt.checksum = compute_checksum(start_pkt)
    packets[0] = bytes(start_pkt)

    # DATA
    seq = 1
    for chunk in chunks:
        data_pkt = PacketHeader(type=2, seq_num=seq, length=len(chunk))
        pkt_with_data = data_pkt / chunk
        data_pkt.checksum = compute_checksum(pkt_with_data)
        packets[seq] = bytes(data_pkt / chunk)
        seq += 1

    # END
    end_seq = seq
    end_pkt = PacketHeader(type=1, seq_num=end_seq, length=0)
    end_pkt.checksum = compute_checksum(end_pkt)
    packets[end_seq] = bytes(end_pkt)
    total_packets = end_seq + 1

    base = 0
    next_packet = 0

    # Send packets
    while base < total_packets:
        while next_packet < total_packets and next_packet < base + window_size:
            if next_packet not in acked:
                s.sendto(packets[next_packet], (receiver_ip, receiver_port))
                timers[next_packet] = time.monotonic()
            next_packet += 1

        # Check for ACKs.
        try:
            data, addr = s.recvfrom(2048)
            ack_pkt = PacketHeader(data[:16])
            if ack_pkt.type == 3:
                ack_seq = ack_pkt.seq_num
                acked[ack_seq] = True
                # Slide window if the base packet is acknowledged.
                while base in acked:
                    base += 1
        except socket.timeout:
            pass

        # Selectively retransmit Un-acked, timed out packets.
        current_time = time.monotonic()
        for seq_num in range(base, min(next_packet, total_packets)):
            if seq_num not in acked and current_time - timers.get(seq_num, 0) > 0.5:
                s.sendto(packets[seq_num], (receiver_ip, receiver_port))
                timers[seq_num] = current_time

    s.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receiver_ip", help="The IP address of the host that receiver is running on")
    parser.add_argument("receiver_port", type=int, help="The port number on which receiver is listening")
    parser.add_argument("window_size", type=int, help="Maximum number of outstanding packets")
    args = parser.parse_args()

    sender(args.receiver_ip, args.receiver_port, args.window_size)

if __name__ == "__main__":
    main()
