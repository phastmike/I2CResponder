from machine import mem32, mem8, Pin


class I2CResponder:
    # Register base addresses
    I2C0_BASE = 0x40044000
    I2C1_BASE = 0x40048000
    IO_BANK0_BASE = 0x40014000

    # Register access method control flags
    REG_ACCESS_METHOD_RW = 0x0000
    REG_ACCESS_METHOD_XOR = 0x1000
    REG_ACCESS_METHOD_SET = 0x2000
    REG_ACCESS_METHOD_CLR = 0x3000

    # Register address offsets
    IC_CON = 0
    IC_TAR = 4
    IC_SAR = 8
    IC_DATA_CMD = 0x10
    IC_RAW_INTR_STAT = 0x34
    IC_RX_TL = 0x38
    IC_TX_TL = 0x3C
    IC_CLR_INTR = 0x40
    IC_CLR_RD_REQ = 0x50
    IC_CLR_TX_ABRT = 0x54
    IC_ENABLE = 0x6C
    IC_STATUS = 0x70

    BIT_RFNE = 0x08 # Receive FIFO Not Empty

    def write_reg(self, register_offset, data, method=0):
        mem32[self.i2c_base | method | register_offset] = data

    def set_reg(self, register_offset, data):
        self.write_reg(register_offset, data, method=self.REG_ACCESS_METHOD_SET)

    def clr_reg(self, register_offset, data):
        self.write_reg(register_offset, data, method=self.REG_ACCESS_METHOD_CLR)

    def __init__(self, i2cID=0, sda_gpio=0, scl_gpio=1, responder_address=0x41):
        self.scl = scl_gpio
        self.sda = sda_gpio
        self.responder_address = responder_address
        self.i2c_ID = i2cID
        if self.i2c_ID == 0:
            self.i2c_base = self.I2C0_BASE
        else:
            self.i2c_base = self.I2C1_BASE

        # 1 Disable DW_apb_i2c
        self.clr_reg(self.IC_ENABLE, 1)
        # 2 set responder address
        # clr bit 0 to 9
        # set responder address
        self.clr_reg(self.IC_SAR, 0x1FF)
        self.set_reg(self.IC_SAR, self.responder_address & 0x1FF)
        # 3 write IC_CON  7 bit, enable in responder-only
        self.clr_reg(self.IC_CON, 0b01001001)
        # set SDA PIN
        mem32[self.IO_BANK0_BASE | self.REG_ACCESS_METHOD_CLR | (4 + 8 * self.sda)] = 0x1F
        mem32[self.IO_BANK0_BASE | self.REG_ACCESS_METHOD_SET | (4 + 8 * self.sda)] = 3
        # set SLA PIN
        mem32[self.IO_BANK0_BASE | self.REG_ACCESS_METHOD_CLR | (4 + 8 * self.scl)] = 0x1F
        mem32[self.IO_BANK0_BASE | self.REG_ACCESS_METHOD_SET | (4 + 8 * self.scl)] = 3
        # 4 enable i2c
        self.set_reg(self.IC_ENABLE, 1)

    def anyRead(self):
        status = mem32[self.i2c_base | self.IC_RAW_INTR_STAT] & 0x20
        if status:
            return True
        return False

    def put(self, data):
        # reset flag
        self.clr_reg(self.IC_CLR_TX_ABRT, 1)
        status = mem32[self.i2c_base | self.IC_CLR_RD_REQ]
        mem32[self.i2c_base | self.IC_DATA_CMD] = data & 0xFF

    def rx_data_is_available(self):
        """Check whether incoming (I2C write) data is available

        Returns:
            True if data is available, False otherwise.
        """
        # get IC_STATUS
        status = mem32[self.i2c_base | self.IC_STATUS]
        # Check RFNE (Receive FIFO not empty)
        if status & self.BIT_RFNE:
            # There is data in the Zx FIFO
            return True
        # The Rx FIFO is empty
        return False

    def get_rx_data(self, max_size=1):
        """Get incoming (I2C write) data.

        Will return bytes from the Rx FIFO, if present, up to the requested size.

        Args:
            max_size [int]: The maximum number of bytes to fetch.
        Returns:
            A list containing 0 to max_size bytes.
        """
        data = []
        while len(data) < max_size and self.rx_data_is_available():
            data.append(mem32[self.i2c_base | self.IC_DATA_CMD] & 0xFF)
        return data
