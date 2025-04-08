import argparse
import socket
import sys

from utils import PacketHeader, compute_checksum

def receiver(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((receiver_ip, receiver_port))

    expected = 0
    buffer = {}  # buffer for out-of-order packets
    output = bytearray()
    connection_started = False

    while True:
        pkt, addr = s.recvfrom(2048)
        pkt_header = PacketHeader(pkt[:16])
        data = pkt[16:16 + pkt_header.length]

        received_checksum = pkt_header.checksum
        pkt_header.checksum = 0
        if pkt_header.type in [0, 1]:
            computed = compute_checksum(pkt_header)
        else:
            computed = compute_checksum(pkt_header / data)
        if received_checksum != computed:
            continue

        if pkt_header.type == 0:
            if not connection_started:
                connection_started = True
                expected = 1
            # Send ACK with seq_num 1, not 0, for the START packet.
            ack_pkt = PacketHeader(type=3, seq_num=1, length=0)
            ack_pkt.checksum = compute_checksum(ack_pkt)
            s.sendto(bytes(ack_pkt), addr)
            continue

        # END
        if pkt_header.type == 1:
            if pkt_header.seq_num == expected:
                ack_pkt = PacketHeader(type=3, seq_num=pkt_header.seq_num, length=0)
                ack_pkt.checksum = compute_checksum(ack_pkt)
                s.sendto(bytes(ack_pkt), addr)
                sys.stdout.buffer.write(output)
                sys.stdout.buffer.flush()
                break
            else:
                # Even if out-of-order, still acknowledge END.
                ack_pkt = PacketHeader(type=3, seq_num=pkt_header.seq_num, length=0)
                ack_pkt.checksum = compute_checksum(ack_pkt)
                s.sendto(bytes(ack_pkt), addr)
            continue

        seq = pkt_header.seq_num

        if seq >= expected + window_size:
            continue

        # In-order packet processing.
        if seq == expected:
            output.extend(data)
            expected += 1
            # Process any buffered consecutive packets.
            while expected in buffer:
                output.extend(buffer.pop(expected))
                expected += 1
            # Send ACK with the same seq_num as received (for DATA packets).
            ack_pkt = PacketHeader(type=3, seq_num=pkt_header.seq_num, length=0)
            ack_pkt.checksum = compute_checksum(ack_pkt)
            s.sendto(bytes(ack_pkt), addr)
        else:
            # Out-of-order but within window: buffer and ack individually.
            if seq not in buffer:
                buffer[seq] = data
            ack_pkt = PacketHeader(type=3, seq_num=pkt_header.seq_num, length=0)
            ack_pkt.checksum = compute_checksum(ack_pkt)
            s.sendto(bytes(ack_pkt), addr)

    s.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receiver_ip", help="The IP address of the host that receiver is running on")
    parser.add_argument("receiver_port", type=int, help="The port number on which receiver is listening")
    parser.add_argument("window_size", type=int, help="Maximum number of outstanding packets")
    args = parser.parse_args()

    receiver(args.receiver_ip, args.receiver_port, args.window_size)

if __name__ == "__main__":
    main()
