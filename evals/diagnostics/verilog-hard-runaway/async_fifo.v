module async_fifo #(parameter WIDTH = 8, parameter DEPTH = 8)
  (input  wire             wclk,
   input  wire             wrst_n,
   input  wire             winc,
   input  wire [WIDTH-1:0] wdata,
   output wire             wfull,
   input  wire             rclk,
   input  wire             rrst_n,
   input  wire             rinc,
   output wire [WIDTH-1:0] rdata,
   output wire             rempty);

  localparam AW = 1;
  // compute address width
  localparam AW_CALC = (DEPTH <= 2)   ? 1 :
                       (DEPTH <= 4)   ? 2 :
                       (DEPTH <= 8)   ? 3 :
                       (DEPTH <= 16)  ? 4 :
                       (DEPTH <= 32)  ? 5 :
                       (DEPTH <= 64)  ? 6 :
                       (DEPTH <= 128) ? 7 :
                       (DEPTH <= 256) ? 8 :
                       (DEPTH <= 512) ? 9 : 10;
  localparam PW = AW_CALC + 1;

  reg [WIDTH-1:0] mem [0:DEPTH-1];

  // Write domain pointers
  reg  [PW-1:0] wbin, wptr_gray;
  wire [PW-1:0] wbin_next, wptr_gray_next;
  reg  [PW-1:0] rptr_gray_wq1, rptr_gray_wq2;

  // Read domain pointers
  reg  [PW-1:0] rbin, rptr_gray;
  wire [PW-1:0] rbin_next, rptr_gray_next;
  reg  [PW-1:0] wptr_gray_rq1, wptr_gray_rq2;

  // Binary to Gray
  function [PW-1:0] bin2gray;
    input [PW-1:0] b;
    begin
      bin2gray = (b >> 1) ^ b;
    end
  endfunction

  wire [AW_CALC-1:0] waddr = wbin[AW_CALC-1:0];
  wire [AW_CALC-1:0] raddr = rbin[AW_CALC-1:0];

  // Write pointer logic
  always @(posedge wclk or negedge wrst_n) begin
    if (!wrst_n) begin
      wbin          <= {PW{1'b0}};
      wptr_gray     <= {PW{1'b0}};
      rptr_gray_wq1 <= {PW{1'b0}};
      rptr_gray_wq2 <= {PW{1'b0}};
    end else begin
      rptr_gray_wq1 <= rptr_gray;
      rptr_gray_wq2 <= rptr_gray_wq1;
      wbin          <= wbin_next;
      wptr_gray     <= wptr_gray_next;
    end
  end

  assign wbin_next      = wbin + {{(PW-1){1'b0}}, (winc & ~wfull)};
  assign wptr_gray_next = bin2gray(wbin_next);
  assign wfull          = (wptr_gray_next == {~rptr_gray_wq2[PW-1:PW-2],
                                              rptr_gray_wq2[PW-3:0]});

  // Read pointer logic
  always @(posedge rclk or negedge rrst_n) begin
    if (!rrst_n) begin
      rbin          <= {PW{1'b0}};
      rptr_gray     <= {PW{1'b0}};
      wptr_gray_rq1 <= {PW{1'b0}};
      wptr_gray_rq2 <= {PW{1'b0}};
    end else begin
      wptr_gray_rq1 <= wptr_gray;
      wptr_gray_rq2 <= wptr_gray_rq1;
      rbin          <= rbin_next;
      rptr_gray     <= rptr_gray_next;
    end
  end

  assign rbin_next      = rbin + {{(PW-1){1'b0}}, (rinc & ~rempty)};
  assign rptr_gray_next = bin2gray(rbin_next);
  assign rempty         = (rptr_gray_next == wptr_gray_rq2);

  // Memory
  always @(posedge wclk) begin
    if (winc & ~wfull)
      mem[waddr] <= wdata;
  end

  assign rdata = mem[raddr];

endmodule
