// Name: Junyong Zhao
// PennKey: junyong

/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>


/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

header ethernet_t {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}

header ipv4_t {
    // DONE
    bit<4>  version;
    bit<4>  ihl;
    bit<8>  diffserv;
    bit<16> totalLen;
    bit<16> identification;
    bit<3>  flags;
    bit<13> fragOffset;
    bit<8>  ttl;
    bit<8>  protocol;
    bit<16> hdrChecksum;
    bit<32> srcAddr;
    bit<32> dstAddr;
}

header arp_t {
    // DONE
    bit<16> htype;
    bit<16> ptype;
    bit<8>  hlen;
    bit<8>  plen;
    bit<16> oper;
    bit<48> sha;
    bit<32> spa;
    bit<48> tha;
    bit<32> tpa;
}

struct headers_t {
    ethernet_t  ethernet;
    ipv4_t      ipv4;
    arp_t       arp;
}


struct local_variables_t {
    bit<1> forMe;
    // DONE
    bit<32> tpa;
}


/*************************************************************************
***********************  P A R S E   P A C K E T *************************
*************************************************************************/

parser cis553Parser(packet_in packet,
                    out headers_t hdr,
                    inout local_variables_t metadata,
                    inout standard_metadata_t standard_metadata) {
    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            0x0800: parse_ipv4;
            0x0806: parse_arp;
            default: accept;
        }
    }

    state parse_arp {
        packet.extract(hdr.arp);
        transition accept;
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition accept;
    }
}


/*************************************************************************
***********************  I N G R E S S  **********************************
*************************************************************************/

control cis553Ingress(inout headers_t hdr,
                      inout local_variables_t metadata,
                      inout standard_metadata_t standard_metadata) {
    action aiForMe() {
        metadata.forMe = 1;
    }

    action aiNotForMe() {
        metadata.forMe = 0;
    }

    // Our router is an endpoint on every Ethernet LAN where it is attached.
    // Just like other endpoints, e.g., hosts, it will only listen for L2
    // messages that are addressed to it.
    table tiHandleEthernet {
        key = {
            hdr.ethernet.dstAddr : exact;
            standard_metadata.ingress_port : exact;
        }
        actions = {
            aiForMe;
            aiNotForMe;
        }
    }

    action aDrop() {
        mark_to_drop(standard_metadata);
    }

    action aiArpResponse(bit<48> src_mac) {
        hdr.arp.oper = 2;
        metadata.tpa = hdr.arp.spa;
        hdr.arp.spa = hdr.arp.tpa;
        hdr.arp.tpa = metadata.tpa;
        hdr.arp.tha = hdr.arp.sha;
        hdr.arp.sha = src_mac;
        standard_metadata.egress_spec = standard_metadata.ingress_port;
    }

    // Respond to ARP requests for our IP to tell the requester that packets
    // sent to our IP should be addressed, at Layer-2, to our MAC address.
    table tiArpResponse {
        // DONE
        key = {
            hdr.arp.tpa : exact;
            hdr.arp.oper : exact;
        }
        actions = {
            aiArpResponse;
            aDrop;
        }
        default_action = aDrop();
    }

    action aiForward(bit<48> src_mac, bit<48> dst_mac, bit<9> egress_port) {
        hdr.ethernet.srcAddr = src_mac;
        hdr.ethernet.dstAddr = dst_mac;
        standard_metadata.egress_spec = egress_port;
    }

    // Look up the IP of the next hop on the route using a Longest Prefix Match
    // (lpm) rather than an exact match
    table tiIpv4Lpm {
        // DONE
        key = {
            hdr.ipv4.dstAddr : lpm;
        }
        actions = {
            aiForward;
            aDrop;
        }
        default_action = aDrop();
    }

    // Given an IP, look up the destination MAC address and physical port.
    // This serves the same purpose as the hosts' ARP tables, but here it's okay
    // to hardcode the values.
    table tiArpLookup {
        // DONE
        key = {
            hdr.ipv4.dstAddr : lpm;
        }
        actions = {
            aiForward;
        }
    }

    apply {
        tiHandleEthernet.apply();

        if (metadata.forMe == 0) {
            aDrop();
        } else if (hdr.arp.isValid()) {
            tiArpResponse.apply();
        } else if (hdr.ipv4.isValid()) {
            tiIpv4Lpm.apply();
            tiArpLookup.apply();
        } else {
            aDrop();
        }
    }
}


/*************************************************************************
***********************  E G R E S S  ************************************
*************************************************************************/

control cis553Egress(inout headers_t hdr,
                     inout local_variables_t metadata,
                     inout standard_metadata_t standard_metadata) {
    apply { }
}


/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control cis553VerifyChecksum(inout headers_t hdr,
                             inout local_variables_t metadata) {
     apply { }
}


/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   ***************
*************************************************************************/

control cis553ComputeChecksum(inout headers_t hdr,
                              inout local_variables_t metadata) {
    // The switch handles the Ethernet checksum, so we don't need to deal with
    // that, but we do need to deal with the IP checksum!
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version,
              hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}


/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   ********************
*************************************************************************/

control cis553Deparser(packet_out packet, in headers_t hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.arp);
        packet.emit(hdr.ipv4);
    }
}


/*************************************************************************
***********************  S W I T C H  ************************************
*************************************************************************/

V1Switch(cis553Parser(),
         cis553VerifyChecksum(),
         cis553Ingress(),
         cis553Egress(),
         cis553ComputeChecksum(),
         cis553Deparser()) main;
