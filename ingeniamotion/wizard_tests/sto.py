from enum import IntEnum
from typing import TYPE_CHECKING, List, Optional

import ingenialogger

from ingeniamotion.enums import SeverityLevel
from ingeniamotion.wizard_tests.base_test import BaseTest, LegacyDictReportType

if TYPE_CHECKING:
    from ingeniamotion import MotionController


class STOTest(BaseTest[LegacyDictReportType]):
    """STO test."""

    class ResultType(IntEnum):
        STO_INACTIVE = 0
        STO_ACTIVE = -1
        STO_ABNORMAL_LATCHED = -2
        STO_ABNORMAL = -3
        STO_ABNORMAL_SUPPLY = -4
        STO_INPUTS_DIFFER = -5

    class Polarity(IntEnum):
        NORMAL = 0
        REVERSED = 1

    result_description = {
        ResultType.STO_INACTIVE: "STO Inactive",
        ResultType.STO_ACTIVE: "STO Active",
        ResultType.STO_ABNORMAL_LATCHED: "Abnormal STO Latched",
        ResultType.STO_ABNORMAL: "Abnormal STO",
        ResultType.STO_ABNORMAL_SUPPLY: "Abnormal Supply",
        ResultType.STO_INPUTS_DIFFER: "STO Inputs Differ",
    }

    STO_STATUS_REGISTER = "DRV_PROT_STO_STATUS"

    STO1_ACTIVE_BIT = 0x1
    STO2_ACTIVE_BIT = 0x2
    STO_SUPPLY_FAULT_BIT = 0x4
    STO_ABNORMAL_FAULT_BIT = 0x8
    STO_REPORT_BIT = 0x10

    BACKUP_REGISTERS: List[str] = []

    def __init__(
        self, mc: "MotionController", servo: str, axis: int, logger_drive_name: Optional[str] = None
    ) -> None:
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.axis = axis
        if logger_drive_name is None:
            self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=mc.servo_name(servo))
        else:
            self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=logger_drive_name)
        self.backup_registers_names = self.BACKUP_REGISTERS
        self.suggested_registers = {}
        self.TEST_TYPE = self.ResultType

    def setup(self) -> None:
        pass

    def teardown(self) -> None:
        pass

    def loop(self) -> ResultType:
        if self.mc.configuration.is_sto1_active(servo=self.servo, axis=self.axis):
            self.logger.info("STO1 bit is LOW")
        # Check STO1 status --> Check bit 0 (0x1 in HEX)
        else:
            self.logger.info("STO1 bit is HIGH")

        if self.mc.configuration.is_sto2_active(servo=self.servo, axis=self.axis):
            self.logger.info("STO2 bit is LOW")
        # Check STO2 status --> Check bit 1 (0x2 in HEX)
        else:
            self.logger.info("STO2 bit is HIGH")

        # Check STO supply fault status --> Check bit 2 (0x4 in HEX)
        sto_power_supply = self.mc.configuration.check_sto_power_supply(
            servo=self.servo, axis=self.axis
        )
        if sto_power_supply == 0:
            self.logger.info("STO Power Supply is LOW")
        else:
            self.logger.info("STO Power Supply is HIGH")

        # Check STO abnormal fault status --> Check bit 3 (0x8 in HEX)
        sto_abnormal_fault = self.mc.configuration.is_sto_abnormal_fault(
            servo=self.servo, axis=self.axis
        )
        if not sto_abnormal_fault:
            self.logger.info("STO abnormal fault bit is LOW")
        else:
            self.logger.info("STO abnormal fault bit is HIGH")

        # Check STO abnormal latch status --> Check bits 3(0x8 in HEX), 1(0x2) & 0(0x1)
        sto_abnormal_latch = self.mc.configuration.is_sto_abnormal_latched(
            servo=self.servo, axis=self.axis
        )

        # Check STO report --> Check bit 4 (0x10 in HEX)
        sto_report_bit = self.mc.configuration.get_sto_report_bit(servo=self.servo, axis=self.axis)
        if not sto_report_bit:
            self.logger.info("STO report is LOW")
        else:
            self.logger.info("STO report is HIGH")

        # Check STO STATE
        if self.mc.configuration.is_sto_active(servo=self.servo, axis=self.axis):
            # STO Status in Active State --> STO Active
            return self.ResultType.STO_ACTIVE
        elif not sto_power_supply:
            # STO Supply Fault bit LOW --> STO Supply Fault
            return self.ResultType.STO_ABNORMAL_SUPPLY
        elif sto_abnormal_fault:
            # STO Abnormal Fault bit HIGH
            if sto_abnormal_latch == SeverityLevel.SUCCESS:
                return self.ResultType.STO_ABNORMAL_LATCHED
            elif sto_abnormal_latch == SeverityLevel.WARNING:
                return self.ResultType.STO_ABNORMAL
        elif self.mc.configuration.is_sto_inactive(servo=self.servo, axis=self.axis):
            # STO Status in Inactive State --> STO Inactive
            return self.ResultType.STO_INACTIVE
        else:
            # STO Unknown state
            return self.ResultType.STO_INPUTS_DIFFER

    def get_result_msg(self, output: ResultType) -> str:
        return self.result_description[output]

    def get_result_severity(self, output: ResultType) -> SeverityLevel:
        if output < self.ResultType.STO_INACTIVE:
            return SeverityLevel.FAIL
        else:
            return SeverityLevel.SUCCESS
