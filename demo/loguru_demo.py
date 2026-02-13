from loguru import logger


logger.add("app.log", level="INFO")
logger.info("应用启动")
logger.debug("调试信息")
logger.error("错误信息")
logger.warning("警告信息")
