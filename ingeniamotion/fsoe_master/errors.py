from ingeniamotion.errors import Error, ErrorQueueDescriptor

MCUA_ERROR_QUEUE = ErrorQueueDescriptor(
    last_error_reg_uid="FSOE_LAST_ERROR_MCUA",
    total_error_reg_uid="FSOE_TOTAL_ERROR_MCUA",
    error_request_index_reg_uid="FSOE_ERROR_REQUEST_INDEX_MCUA",
    error_request_code_reg_uid="FSOE_ERROR_REQUEST_CODE_MCUA",
    max_index_request=31,
    error_type=Error,
)

MCUB_ERROR_QUEUE = ErrorQueueDescriptor(
    last_error_reg_uid="FSOE_LAST_ERROR_MCUB",
    total_error_reg_uid="FSOE_TOTAL_ERROR_MCUB",
    error_request_index_reg_uid="FSOE_ERROR_REQUEST_INDEX_MCUB",
    error_request_code_reg_uid="FSOE_ERROR_REQUEST_CODE_MCUB",
    max_index_request=31,
    error_type=Error,
)
