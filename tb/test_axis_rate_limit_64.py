#!/usr/bin/env python
"""

Copyright (c) 2014-2018 Alex Forencich

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

"""

from myhdl import *
import os

import axis_ep

module = 'axis_rate_limit'
testbench = 'test_%s_64' % module

srcs = []

srcs.append("../rtl/%s.v" % module)
srcs.append("%s.v" % testbench)

src = ' '.join(srcs)

build_cmd = "iverilog -o %s.vvp %s" % (testbench, src)

def bench():

    # Parameters
    DATA_WIDTH = 64
    KEEP_ENABLE = (DATA_WIDTH>8)
    KEEP_WIDTH = (DATA_WIDTH/8)
    LAST_ENABLE = 1
    ID_ENABLE = 1
    ID_WIDTH = 8
    DEST_ENABLE = 1
    DEST_WIDTH = 8
    USER_ENABLE = 1
    USER_WIDTH = 1

    # Inputs
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    current_test = Signal(intbv(0)[8:])

    input_axis_tdata = Signal(intbv(0)[DATA_WIDTH:])
    input_axis_tkeep = Signal(intbv(1)[KEEP_WIDTH:])
    input_axis_tvalid = Signal(bool(0))
    input_axis_tlast = Signal(bool(0))
    input_axis_tid = Signal(intbv(0)[ID_WIDTH:])
    input_axis_tdest = Signal(intbv(0)[DEST_WIDTH:])
    input_axis_tuser = Signal(intbv(0)[USER_WIDTH:])
    output_axis_tready = Signal(bool(0))

    rate_num = Signal(intbv(0)[8:])
    rate_denom = Signal(intbv(0)[8:])
    rate_by_frame = Signal(bool(0))

    # Outputs
    input_axis_tready = Signal(bool(0))
    output_axis_tdata = Signal(intbv(0)[DATA_WIDTH:])
    output_axis_tkeep = Signal(intbv(1)[KEEP_WIDTH:])
    output_axis_tvalid = Signal(bool(0))
    output_axis_tlast = Signal(bool(0))
    output_axis_tid = Signal(intbv(0)[ID_WIDTH:])
    output_axis_tdest = Signal(intbv(0)[DEST_WIDTH:])
    output_axis_tuser = Signal(intbv(0)[USER_WIDTH:])

    # sources and sinks
    source_pause = Signal(bool(0))
    sink_pause = Signal(bool(0))

    source = axis_ep.AXIStreamSource()

    source_logic = source.create_logic(
        clk,
        rst,
        tdata=input_axis_tdata,
        tkeep=input_axis_tkeep,
        tvalid=input_axis_tvalid,
        tready=input_axis_tready,
        tlast=input_axis_tlast,
        tid=input_axis_tid,
        tdest=input_axis_tdest,
        tuser=input_axis_tuser,
        pause=source_pause,
        name='source'
    )

    sink = axis_ep.AXIStreamSink()

    sink_logic = sink.create_logic(
        clk,
        rst,
        tdata=output_axis_tdata,
        tkeep=output_axis_tkeep,
        tvalid=output_axis_tvalid,
        tready=output_axis_tready,
        tlast=output_axis_tlast,
        tid=output_axis_tid,
        tdest=output_axis_tdest,
        tuser=output_axis_tuser,
        pause=sink_pause,
        name='sink'
    )

    # DUT
    if os.system(build_cmd):
        raise Exception("Error running build command")

    dut = Cosimulation(
        "vvp -m myhdl %s.vvp -lxt2" % testbench,
        clk=clk,
        rst=rst,
        current_test=current_test,

        input_axis_tdata=input_axis_tdata,
        input_axis_tkeep=input_axis_tkeep,
        input_axis_tvalid=input_axis_tvalid,
        input_axis_tready=input_axis_tready,
        input_axis_tlast=input_axis_tlast,
        input_axis_tid=input_axis_tid,
        input_axis_tdest=input_axis_tdest,
        input_axis_tuser=input_axis_tuser,

        output_axis_tdata=output_axis_tdata,
        output_axis_tkeep=output_axis_tkeep,
        output_axis_tvalid=output_axis_tvalid,
        output_axis_tready=output_axis_tready,
        output_axis_tlast=output_axis_tlast,
        output_axis_tid=output_axis_tid,
        output_axis_tdest=output_axis_tdest,
        output_axis_tuser=output_axis_tuser,

        rate_num=rate_num,
        rate_denom=rate_denom,
        rate_by_frame=rate_by_frame
    )

    @always(delay(4))
    def clkgen():
        clk.next = not clk

    reset_stats = Signal(bool(False))
    cur_frame = Signal(bool(False))
    tick_count = Signal(intbv(0))
    byte_count = Signal(intbv(0))
    frame_count = Signal(intbv(0))

    @always(clk.posedge)
    def monitor():
        ctc = int(tick_count)
        cbc = int(byte_count)
        cfc = int(frame_count)
        if reset_stats:
            ctc = 0
            cbc = 0
            cfc = 0
            reset_stats.next = 0
        ctc += len(output_axis_tkeep)
        if output_axis_tready and output_axis_tvalid:
            cbc += bin(output_axis_tkeep).count('1')
            if output_axis_tlast:
                cur_frame.next = False
            elif not cur_frame:
                cfc += 1
                cur_frame.next = True
        tick_count.next = ctc
        byte_count.next = cbc
        frame_count.next = cfc

    @instance
    def check():
        yield delay(100)
        yield clk.posedge
        rst.next = 1
        yield clk.posedge
        rst.next = 0
        yield clk.posedge
        yield delay(100)
        yield clk.posedge

        yield clk.posedge
        rate_num.next = 1
        rate_denom.next = 4
        rate_by_frame.next = 1

        for frame_mode in (True, False):
            print("test frame mode %s" % frame_mode)
            rate_by_frame.next = frame_mode

            rate_num.next = 1
            rate_denom.next = 4

            yield clk.posedge
            print("test 1: test packet")
            current_test.next = 1

            test_frame = axis_ep.AXIStreamFrame(
                b'\xDA\xD1\xD2\xD3\xD4\xD5' +
                b'\x5A\x51\x52\x53\x54\x55' +
                b'\x80\x00' +
                b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10',
                id=1,
                dest=1
            )

            source.send(test_frame)

            yield sink.wait()
            rx_frame = sink.recv()

            assert rx_frame == test_frame

            yield delay(100)

            yield clk.posedge
            print("test 2: longer packet")
            current_test.next = 2

            test_frame = axis_ep.AXIStreamFrame(
                b'\xDA\xD1\xD2\xD3\xD4\xD5' +
                b'\x5A\x51\x52\x53\x54\x55' +
                b'\x80\x00' +
                bytearray(range(256)),
                id=2,
                dest=1
            )

            source.send(test_frame)

            yield sink.wait()
            rx_frame = sink.recv()

            assert rx_frame == test_frame

            yield clk.posedge
            print("test 3: test packet with pauses")
            current_test.next = 3

            test_frame = axis_ep.AXIStreamFrame(
                b'\xDA\xD1\xD2\xD3\xD4\xD5' +
                b'\x5A\x51\x52\x53\x54\x55' +
                b'\x80\x00' +
                bytearray(range(256)),
                id=3,
                dest=1
            )

            source.send(test_frame)
            yield clk.posedge

            yield delay(64)
            yield clk.posedge
            source_pause.next = True
            yield delay(32)
            yield clk.posedge
            source_pause.next = False

            yield delay(64)
            yield clk.posedge
            sink_pause.next = True
            yield delay(32)
            yield clk.posedge
            sink_pause.next = False

            yield sink.wait()
            rx_frame = sink.recv()

            assert rx_frame == test_frame

            yield delay(100)

            yield clk.posedge
            print("test 4: back-to-back packets")
            current_test.next = 4

            test_frame1 = axis_ep.AXIStreamFrame(
                b'\xDA\xD1\xD2\xD3\xD4\xD5' +
                b'\x5A\x51\x52\x53\x54\x55' +
                b'\x80\x00' +
                b'\x01\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10',
                id=4,
                dest=1
            )
            test_frame2 = axis_ep.AXIStreamFrame(
                b'\xDA\xD1\xD2\xD3\xD4\xD5' +
                b'\x5A\x51\x52\x53\x54\x55' +
                b'\x80\x00' +
                b'\x02\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10',
                id=4,
                dest=2
            )

            source.send(test_frame1)
            source.send(test_frame2)

            yield sink.wait()
            rx_frame = sink.recv()

            assert rx_frame == test_frame1

            yield sink.wait()
            rx_frame = sink.recv()

            assert rx_frame == test_frame2

            yield delay(100)

            yield clk.posedge
            print("test 5: alternate pause source")
            current_test.next = 5

            test_frame1 = axis_ep.AXIStreamFrame(
                b'\xDA\xD1\xD2\xD3\xD4\xD5' +
                b'\x5A\x51\x52\x53\x54\x55' +
                b'\x80\x00' +
                b'\x01\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10',
                id=5,
                dest=1
            )
            test_frame2 = axis_ep.AXIStreamFrame(
                b'\xDA\xD1\xD2\xD3\xD4\xD5' +
                b'\x5A\x51\x52\x53\x54\x55' +
                b'\x80\x00' +
                b'\x02\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10',
                id=5,
                dest=2
            )

            source.send(test_frame1)
            source.send(test_frame2)
            yield clk.posedge

            while input_axis_tvalid or output_axis_tvalid:
                source_pause.next = True
                yield clk.posedge
                yield clk.posedge
                yield clk.posedge
                source_pause.next = False
                yield clk.posedge

            yield sink.wait()
            rx_frame = sink.recv()

            assert rx_frame == test_frame1

            yield sink.wait()
            rx_frame = sink.recv()

            assert rx_frame == test_frame2

            yield delay(100)

            yield clk.posedge
            print("test 6: alternate pause sink")
            current_test.next = 6

            test_frame1 = axis_ep.AXIStreamFrame(
                b'\xDA\xD1\xD2\xD3\xD4\xD5' +
                b'\x5A\x51\x52\x53\x54\x55' +
                b'\x80\x00' +
                b'\x01\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10',
                id=6,
                dest=1
            )
            test_frame2 = axis_ep.AXIStreamFrame(
                b'\xDA\xD1\xD2\xD3\xD4\xD5' +
                b'\x5A\x51\x52\x53\x54\x55' +
                b'\x80\x00' +
                b'\x02\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10',
                id=6,
                dest=2
            )

            source.send(test_frame1)
            source.send(test_frame2)
            yield clk.posedge

            while input_axis_tvalid or output_axis_tvalid:
                sink_pause.next = True
                yield clk.posedge
                yield clk.posedge
                yield clk.posedge
                sink_pause.next = False
                yield clk.posedge

            yield sink.wait()
            rx_frame = sink.recv()

            assert rx_frame == test_frame1

            yield sink.wait()
            rx_frame = sink.recv()

            assert rx_frame == test_frame2

            yield delay(100)

            yield clk.posedge
            print("test 7: tuser assert")
            current_test.next = 7

            test_frame = axis_ep.AXIStreamFrame(
                b'\xDA\xD1\xD2\xD3\xD4\xD5' +
                b'\x5A\x51\x52\x53\x54\x55' +
                b'\x80\x00' +
                b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10',
                id=7,
                dest=1,
                last_cycle_user=1
            )

            source.send(test_frame)

            yield sink.wait()
            rx_frame = sink.recv()

            assert rx_frame == test_frame
            assert rx_frame.last_cycle_user

            yield delay(100)

            yield clk.posedge
            print("test 8: various lengths and delays")
            current_test.next = 8

            for rate in ((1,1), (1,2), (1,10), (2,3)):
                print("test 8 rate %d / %d" % rate)
                rate_num.next = rate[0]
                rate_denom.next = rate[1]

                yield delay(100)

                reset_stats.next = 1
                yield clk.posedge
                start_time = now()

                lens = [32, 48, 64, 96, 128, 256]
                test_frame = []

                for i in range(len(lens)):
                    test_frame.append(axis_ep.AXIStreamFrame(
                        b'\xDA\xD1\xD2\xD3\xD4\xD5' +
                        b'\x5A\x51\x52\x53\x54\x55' +
                        b'\x80\x00' +
                        bytearray(range(lens[i])),
                        id=i,
                        dest=1
                    ))

                for f in test_frame:
                    source.send(f)

                rx_frame = []

                for i in range(len(lens)):
                    yield sink.wait()
                    rx_frame.append(sink.recv())

                yield clk.posedge

                while not input_axis_tready:
                    yield clk.posedge

                stop_time = now()

                assert len(rx_frame) == len(test_frame)

                for i in range(len(lens)):
                    assert rx_frame[i] == test_frame[i]

                cycle = (stop_time - start_time) / 8

                print("cycles %d" % cycle)
                print("tick count %d" % tick_count)
                print("byte count %d" % byte_count)
                print("frame count %d" % frame_count)

                assert tick_count == cycle*len(output_axis_tkeep)
                assert byte_count == sum(len(f.data) for f in test_frame)
                assert frame_count == len(test_frame)

                test_rate = float(rate_num) / float(rate_denom)
                meas_rate = float(byte_count) / float(tick_count)
                error = (test_rate - meas_rate) / test_rate

                print("test rate %f" % test_rate)
                print("meas rate %f" % meas_rate)
                print("error %f%%" % (error*100))

                assert abs(error) < 0.1

                yield delay(100)

        raise StopSimulation

    return instances()

def test_bench():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sim = Simulation(bench())
    sim.run()

if __name__ == '__main__':
    print("Running test...")
    test_bench()

