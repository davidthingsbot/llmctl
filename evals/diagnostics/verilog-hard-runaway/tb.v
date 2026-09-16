
module tb;
  localparam WIDTH = 8, DEPTH = 8;
  reg wclk = 0, rclk = 0, wrst_n = 0, rrst_n = 0, winc = 0, rinc = 0;
  reg [WIDTH-1:0] wdata = 0;
  wire [WIDTH-1:0] rdata;
  wire wfull, rempty;
  integer pass = 0, fail = 0, errors = 0, got = 0, i;
  reg [WIDTH-1:0] seen;

  async_fifo #(.WIDTH(WIDTH), .DEPTH(DEPTH)) dut (
    .wclk(wclk), .wrst_n(wrst_n), .winc(winc), .wdata(wdata), .wfull(wfull),
    .rclk(rclk), .rrst_n(rrst_n), .rinc(rinc), .rdata(rdata), .rempty(rempty));

  always #5 wclk = ~wclk;   // unrelated clocks, deliberately not integer-related
  always #7 rclk = ~rclk;

  task check(input integer id, input cond);
    begin
      if (cond) begin pass = pass + 1; $display("CHECK %0d PASS", id); end
      else      begin fail = fail + 1; $display("CHECK %0d FAIL", id); end
    end
  endtask

  // one write, driven strictly from the write clock
  task push(input [WIDTH-1:0] value);
    begin
      @(negedge wclk);
      while (wfull) @(negedge wclk);
      wdata = value; winc = 1;
      @(negedge wclk);
      winc = 0;
    end
  endtask

  // one read, driven strictly from the read clock; rdata is sampled while the
  // read pointer still addresses the entry being popped
  task pop(output [WIDTH-1:0] value);
    begin
      @(negedge rclk);
      while (rempty) @(negedge rclk);
      value = rdata; rinc = 1;
      @(negedge rclk);
      rinc = 0;
    end
  endtask

  initial begin
    #23 wrst_n = 1; rrst_n = 1;
    repeat (4) @(negedge rclk);
    check(0, rempty === 1'b1);

    // fill, drain, twice — the second pass exercises pointer wrap
    for (i = 0; i < 2 * DEPTH; i = i + 1) begin
      push(i[WIDTH-1:0]);
      pop(seen);
      if (seen !== i[WIDTH-1:0]) errors = errors + 1;
      got = got + 1;
    end
    check(1, got == 2 * DEPTH);
    check(2, errors == 0);

    repeat (6) @(negedge rclk);
    check(3, rempty === 1'b1);

    $display("SUMMARY pass=%0d fail=%0d got=%0d errors=%0d", pass, fail, got, errors);
    $finish;
  end

  initial begin
    #200000;
    $display("SUMMARY pass=%0d fail=%0d TIMEOUT", pass, fail);
    $finish;
  end
endmodule
