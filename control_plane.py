# Name: Junyong Zhao
# PennKey: junyong

import argparse
import json
import os
import sys
import threading
from time import sleep

sys.path.append("utils")
import bmv2
import helper
from convert import *


def add_ethernet(router, helper, mac, ingress):
    # add entry to tiHandleEthernet
    table_entry = helper.buildTableEntry(
        table_name="cis553Ingress.tiHandleEthernet",
        match_fields={
            "hdr.ethernet.dstAddr": mac,
            "standard_metadata.ingress_port":  ingress},
        action_name="cis553Ingress.aiForMe")
    router.WriteTableEntry(table_entry)

    # broadcast, set aiForMe
    table_entry = helper.buildTableEntry(
        table_name="cis553Ingress.tiHandleEthernet",
        match_fields={
            "hdr.ethernet.dstAddr": "ff:ff:ff:ff:ff:ff",
            "standard_metadata.ingress_port":  ingress},
        action_name="cis553Ingress.aiForMe")
    router.WriteTableEntry(table_entry)


def add_routing_ipv4(router, helper, src_mac, dst_mac, ip_add, egress):
    # add lpm for ipv4 forwarding, prefix_length is always 32
    table_entry = helper.buildTableEntry(
        table_name="cis553Ingress.tiIpv4Lpm",
        match_fields={"hdr.ipv4.dstAddr": [ip_add, 32]},
        action_name="cis553Ingress.aiForward",
        action_params={
            "src_mac": src_mac,
            "dst_mac": dst_mac,
            "egress_port": egress})
    router.WriteTableEntry(table_entry)


def add_routing_lookup(router, helper, src_mac, dst_mac, ip_add, egress):
    # entry for arp lookup, similar to ipv4 forward
    table_entry = helper.buildTableEntry(
        table_name="cis553Ingress.tiArpLookup",
        match_fields={"hdr.ipv4.dstAddr": [ip_add, 32]},
        action_name="cis553Ingress.aiForward",
        action_params={
            "src_mac": src_mac,
            "dst_mac": dst_mac,
            "egress_port": egress})
    router.WriteTableEntry(table_entry)


def add_arp(router, helper, tpa, src_mac):
    # add entry to arp table, combining the
    # tiArpLoopup & tiArpResponse, oper is always 1
    table_entry = helper.buildTableEntry(
        table_name="cis553Ingress.tiArpResponse",
        match_fields={
            "hdr.arp.tpa": tpa,
            "hdr.arp.oper": 1},
        action_name="cis553Ingress.aiArpResponse",
        action_params={"src_mac": src_mac})
    router.WriteTableEntry(table_entry)


def RunControlPlane(router, id_num, p4info_helper):
    # DONE
    # hardcode address to the router
    h1 = "10.0.1.1"
    h2 = "10.0.2.2"
    h3 = "10.0.3.3"

    r1p1 = "10.0.1.100"
    r2p1 = "10.0.2.100"
    r3p1 = "10.0.3.100"

    h1r1 = "00:00:00:00:01:01"
    r1h1 = "00:00:00:01:01:00"

    h2r2 = "00:00:00:00:02:02"
    r2h2 = "00:00:00:02:01:00"

    h3r3 = "00:00:00:00:03:03"
    r3h3 = "00:00:00:03:01:00"

    r1r2 = "00:00:00:01:02:00"
    r2r1 = "00:00:00:02:02:00"

    r1r3 = "00:00:00:01:03:00"
    r3r1 = "00:00:00:03:02:00"

    r2r3 = "00:00:00:02:03:00"
    r3r2 = "00:00:00:03:03:00"

    if id_num == 1:
        add_ethernet(router, p4info_helper, r1h1, 1)
        add_ethernet(router, p4info_helper, r1r2, 2)
        add_ethernet(router, p4info_helper, r1r3, 3)
        add_routing_lookup(router, p4info_helper, r1h1, h1r1, h1, 1)
        add_routing_ipv4(router, p4info_helper, r1r2, r2r1, h2, 2)
        add_routing_ipv4(router, p4info_helper, r1r3, r3r1, h3, 3)
        add_arp(router, p4info_helper, r1p1, r1h1)
    elif id_num == 2:
        add_ethernet(router, p4info_helper, r2h2, 1)
        add_ethernet(router, p4info_helper, r2r1, 2)
        add_ethernet(router, p4info_helper, r2r3, 3)
        add_routing_ipv4(router, p4info_helper, r2r1, r1r2, h1, 2)
        add_routing_lookup(router, p4info_helper, r2h2, h2r2, h2, 1)
        add_routing_ipv4(router, p4info_helper, r2r3, r3r2, h3, 3)
        add_arp(router, p4info_helper, r2p1, r2h2)
    elif id_num == 3:
        add_ethernet(router, p4info_helper, r3h3, 1)
        add_ethernet(router, p4info_helper, r3r1, 2)
        add_ethernet(router, p4info_helper, r3r2, 3)
        add_routing_ipv4(router, p4info_helper, r3r1, r1r3, h1, 2)
        add_routing_ipv4(router, p4info_helper, r3r2, r2r3, h2, 3)
        add_routing_lookup(router, p4info_helper, r3h3, h3r3, h3, 1)
        add_arp(router, p4info_helper, r3p1, r3h3)
    else:
        pass

    while 1:
        # just stay running forever
        sleep(1)

    router.shutdown()

# Starts a control plane for each switch. Hardcoded for our Mininet topology.


def ConfigureNetwork(p4info_file="build/data_plane.p4info",
                     bmv2_json="build/data_plane.json"):
    p4info_helper = helper.P4InfoHelper(p4info_file)

    threads = []

    print "Connecting to P4Runtime server on r1..."
    r1 = bmv2.Bmv2SwitchConnection('r1', "127.0.0.1:50051", 0)
    r1.MasterArbitrationUpdate()
    r1.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                   bmv2_json_file_path=bmv2_json)
    t = threading.Thread(target=RunControlPlane, args=(r1, 1, p4info_helper))
    t.start()
    threads.append(t)

    print "Connecting to P4Runtime server on r2..."
    r2 = bmv2.Bmv2SwitchConnection('r2', "127.0.0.1:50052", 1)
    r2.MasterArbitrationUpdate()
    r2.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                   bmv2_json_file_path=bmv2_json)
    t = threading.Thread(target=RunControlPlane, args=(r2, 2, p4info_helper))
    t.start()
    threads.append(t)

    print "Connecting to P4Runtime server on r3..."
    r3 = bmv2.Bmv2SwitchConnection('r3', "127.0.0.1:50053", 2)
    r3.MasterArbitrationUpdate()
    r3.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                   bmv2_json_file_path=bmv2_json)
    t = threading.Thread(target=RunControlPlane, args=(r3, 3, p4info_helper))
    t.start()
    threads.append(t)

    for t in threads:
        t.join()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CIS553 P4Runtime Controller')

    parser.add_argument("-b", '--bmv2-json',
                        help="path to BMv2 switch description (json)",
                        type=str, action="store",
                        default="build/data_plane.json")
    parser.add_argument("-c", '--p4info-file',
                        help="path to P4Runtime protobuf description (text)",
                        type=str, action="store",
                        default="build/data_plane.p4info")

    args = parser.parse_args()

    if not os.path.exists(args.p4info_file):
        parser.error("File %s does not exist!" % args.p4info_file)
    if not os.path.exists(args.bmv2_json):
        parser.error("File %s does not exist!" % args.bmv2_json)

    ConfigureNetwork(args.p4info_file, args.bmv2_json)
