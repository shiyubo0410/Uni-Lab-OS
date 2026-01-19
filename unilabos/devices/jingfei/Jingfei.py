import ctypes
import os
from ctypes import *
import time


class JingfeiSpectrometer:
    """京飞光谱仪控制类"""
    
    def __init__(self, dll_name="FLA5000DLL.dll"):
        """初始化光谱仪
        
        Args:
            dll_name: DLL文件名,默认为 FLA5000DLL.dll
        """
        # 获取脚本所在目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dll_path = os.path.join(script_dir, dll_name)
        
        # 加载dll动态库
        print("加载dll动态库")
        self.pDll = WinDLL(dll_path)
        
        # 设置标准文件路径
        print("设置标准文件路径")
        res = self.pDll.Fla4000OpenStandrenFile("")
        print("返回：" + str(res))
        
        # 存储零位和基线数据
        self.zeroline = None
        self.baseline = None
        self.spectro_num = 1  # 默认通道号
    
    def set_integration_time(self, time_ms):
        """设置积分时间
        
        Args:
            time_ms: 积分时间,单位毫秒
            
        Returns:
            int: 返回值,1表示成功,0表示失败
        """
        print(f"设置积分时间: {time_ms}ms")
        fCCDTime = c_float(time_ms)
        res = self.pDll.SetIntegrationTimeF(fCCDTime)
        print("返回：" + str(res))
        return res
    
    def get_original_data(self, spectro_num=1):
        """获取像素对应能量数据
        
        Args:
            spectro_num: 光谱仪通道号,默认为1
            
        Returns:
            list: 2048个像素点的能量数据
        """
        print("获取像素对应能量数据")
        fPixData = (c_float * 2048)()
        for i in range(2048):
            fPixData[i] = 0
        res = self.pDll.IGetOriginalData(fPixData, spectro_num)
        print("返回：" + str(res))
        return list(fPixData)
    
    def get_wave_data(self, start_wave=380, end_wave=780, interval=1, spectro_num=1):
        """获取波长对应能量数据
        
        Args:
            start_wave: 起始波长,单位nm,默认380
            end_wave: 结束波长,单位nm,默认780
            interval: 间隔波长,单位nm,默认1
            spectro_num: 光谱仪通道号,默认为1
            
        Returns:
            tuple: (波长列表, 能量数据列表)
        """
        print(f"获取波长对应能量数据: {start_wave}-{end_wave}nm, 间隔{interval}nm")
        fStartWave = c_float(start_wave)
        fEndWave = c_float(end_wave)
        fInterval = c_float(interval)
        
        data_points = int((end_wave - start_wave) / interval) + 1
        fWaveData = (c_float * data_points)()
        for i in range(data_points):
            fWaveData[i] = 0
        
        res = self.pDll.GetWaveData(fStartWave, fEndWave, fInterval, fWaveData, spectro_num)
        print("返回：" + str(res))
        
        wavelengths = [start_wave + i * interval for i in range(data_points)]
        return wavelengths, list(fWaveData)
    
    def get_zeroline(self, spectro_num=None):
        """获取零位数据(暗光谱)
        
        Args:
            spectro_num: 光谱仪通道号,默认使用实例的spectro_num
            
        Returns:
            list: 2048个像素点的零位数据
        """
        if spectro_num is None:
            spectro_num = self.spectro_num
            
        print(f"获取通道{spectro_num}的零位数据")
        self.zeroline = (c_float * 2048)()
        res = self.pDll.JF_USB_GetZerolineMux(spectro_num, self.zeroline)
        print("返回：" + str(res))
        
        if res == 1:
            print("✓ 零位数据获取成功")
        else:
            print("✗ 零位数据获取失败")
        
        return list(self.zeroline)
    
    def get_baseline(self, spectro_num=None):
        """获取基线数据(参考光谱)
        
        Args:
            spectro_num: 光谱仪通道号,默认使用实例的spectro_num
            
        Returns:
            list: 2048个像素点的基线数据
        """
        if spectro_num is None:
            spectro_num = self.spectro_num
            
        print(f"获取通道{spectro_num}的基线数据")
        self.baseline = (c_float * 2048)()
        res = self.pDll.JF_USB_GetBaselineMux(spectro_num, self.baseline)
        print("返回：" + str(res))
        
        if res == 1:
            print("✓ 基线数据获取成功")
        else:
            print("✗ 基线数据获取失败")
        
        return list(self.baseline)
    
    def get_absorbance(self, start_wave=380, end_wave=780, interval=1, spectro_num=None, verbose=True):
        """获取吸光度数据
        
        注意: 必须先调用 get_zeroline() 和 get_baseline() 才能使用此函数
        
        Args:
            start_wave: 起始波长,单位nm,默认380
            end_wave: 结束波长,单位nm,默认780
            interval: 间隔波长,单位nm,默认1
            spectro_num: 光谱仪通道号,默认使用实例的spectro_num
            verbose: 是否打印详细信息
            
        Returns:
            tuple: (波长列表, 吸光度数据列表)
        """
        if spectro_num is None:
            spectro_num = self.spectro_num
        
        if self.zeroline is None or self.baseline is None:
            if verbose:
                print("警告: 未获取零位或基线数据,请先调用 get_zeroline() 和 get_baseline()")
            return None, None
        
        if verbose:
            print(f"获取通道{spectro_num}的吸光度数据: {start_wave}-{end_wave}nm, 间隔{interval}nm")
        
        fStartWave = c_float(start_wave)
        fEndWave = c_float(end_wave)
        fInterval = c_float(interval)
        
        data_points = int((end_wave - start_wave) / interval) + 1
        fAData = (c_float * data_points)()
        
        res = self.pDll.JF_USB_GetAbsorbanceMux(
            spectro_num,
            fStartWave,
            fEndWave,
            fInterval,
            fAData
        )
        
        if verbose:
            print("返回：" + str(res))
        
        wavelengths = [start_wave + i * interval for i in range(data_points)]
        return wavelengths, list(fAData)
    
    def measure_absorbance_at_wavelength(self, wavelength, spectro_num=None, verbose=False):
        """测量指定波长的吸光度
        
        Args:
            wavelength: 目标波长,单位nm
            spectro_num: 光谱仪通道号,默认使用实例的spectro_num
            verbose: 是否打印详细信息
            
        Returns:
            float: 该波长的吸光度值
        """
        wavelengths, absorbances = self.get_absorbance(
            wavelength, wavelength, 1, spectro_num, verbose
        )
        if absorbances:
            return absorbances[0]
        return None
    
    def measure_absorbance_at_wavelengths(self, wavelengths, spectro_num=None, verbose=False):
        """测量多个指定波长的吸光度
        
        Args:
            wavelengths: 波长列表,单位nm
            spectro_num: 光谱仪通道号,默认使用实例的spectro_num
            verbose: 是否打印详细信息
            
        Returns:
            dict: {波长: 吸光度值}
        """
        results = {}
        for wavelength in wavelengths:
            abs_value = self.measure_absorbance_at_wavelength(wavelength, spectro_num, verbose)
            if abs_value is not None:
                results[wavelength] = abs_value
        return results
    
    def calibrate(self, spectro_num=None):
        """交互式校准流程(获取零位和基线)
        
        Args:
            spectro_num: 光谱仪通道号,默认使用实例的spectro_num
            
        Returns:
            bool: 校准是否成功
        """
        if spectro_num is None:
            spectro_num = self.spectro_num
        
        print("\n========== 开始校准流程 ==========")
        
        # 获取零位
        print("\n步骤1: 获取零位数据")
        print("请遮住光源(暗光谱),然后按Enter键继续...")
        input()
        self.get_zeroline(spectro_num)
        
        # 获取基线
        print("\n步骤2: 获取基线数据")
        print("请移除遮光物,确保管路中只有溶剂(无样品),然后按Enter键继续...")
        input()
        self.get_baseline(spectro_num)
        
        if self.zeroline is not None and self.baseline is not None:
            print("\n✓ 校准完成,可以开始连续监测")
            return True
        else:
            print("\n✗ 校准失败")
            return False
    
    def continuous_monitor_multi_wavelengths(self, wavelengths, interval_sec=1, duration_sec=None, spectro_num=None):
        """连续监测多个波长的吸光度
        
        Args:
            wavelengths: 波长列表,单位nm
            interval_sec: 采样间隔,单位秒
            duration_sec: 监测时长,单位秒(None表示无限监测,按Ctrl+C停止)
            spectro_num: 光谱仪通道号,默认使用实例的spectro_num
            
        Returns:
            list: [(时间戳, {波长: 吸光度}), ...]
        """
        if self.zeroline is None or self.baseline is None:
            print("错误: 未校准,请先调用 calibrate() 方法")
            return None
        
        if spectro_num is None:
            spectro_num = self.spectro_num
        
        print(f"\n========== 开始连续监测 ==========")
        print(f"监测波长: {wavelengths} nm")
        print(f"采样间隔: {interval_sec}秒")
        if duration_sec:
            print(f"监测时长: {duration_sec}秒")
        else:
            print("监测时长: 无限(按Ctrl+C停止)")
        print("-" * 80)
        
        # 打印表头
        header = f"{'时间(秒)':<12}"
        for wl in wavelengths:
            header += f"{wl}nm{'':<10}"
        print(header)
        print("-" * 80)
        
        data_records = []
        start_time = time.time()
        
        try:
            while True:
                current_time = time.time() - start_time
                
                # 获取所有波长的吸光度
                abs_values = self.measure_absorbance_at_wavelengths(wavelengths, spectro_num, verbose=False)
                
                if abs_values:
                    data_records.append((current_time, abs_values))
                    
                    # 打印数据
                    line = f"{current_time:<12.1f}"
                    for wl in wavelengths:
                        line += f"{abs_values.get(wl, 0):<14.4f}"
                    print(line)
                
                # 检查是否达到监测时长
                if duration_sec and current_time >= duration_sec:
                    break
                
                # 等待下次采样
                time.sleep(interval_sec)
                
        except KeyboardInterrupt:
            print("\n" + "="*80)
            print("监测已手动停止")
        
        print("="*80)
        print(f"监测完成,共采集 {len(data_records)} 个数据点")
        return data_records


# 使用示例
if __name__ == "__main__":
    # 创建光谱仪实例
    spectrometer = JingfeiSpectrometer()
    
    # 设置积分时间
    spectrometer.set_integration_time(100)
    
    # 连续监测示例
    print("\n========== 连续监测280nm波长吸光度 ==========")
    
    # 步骤1: 校准(只需要做一次)
    if spectrometer.calibrate():
        # 步骤2: 开始连续监测280nm波长
        target_wavelengths = [280]  # 只监测280nm
        
        print("\n准备开始连续监测280nm波长...")
        print("按Enter键开始监测...")
        input()
        
        # 连续监测
        data = spectrometer.continuous_monitor_multi_wavelengths(
            wavelengths=target_wavelengths,
            interval_sec=0.5,     # 每0.5秒采样一次
            duration_sec=None     # 无限监测,用Ctrl+C停止
        )
        
        if data:
            print(f"\n监测数据已保存,共{len(data)}条记录")

