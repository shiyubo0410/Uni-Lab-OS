import ctypes
import json
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
    
    def get_absorbance(self, start_wave=380, end_wave=780, interval=1, spectro_num=None, verbose=False):
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
    
    def load_calibration(self, filepath=None):
        """从JSON文件加载已保存的零位和基线校准数据
        
        Args:
            filepath: 校准数据文件路径,默认使用脚本目录下的 calibration_data.json
            
        Returns:
            bool: 加载是否成功
        """
        if filepath is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(script_dir, "calibration_data.json")
        
        print(f"从文件加载校准数据: {filepath}")
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            zeroline_data = data.get('zeroline')
            baseline_data = data.get('baseline')
            spectro_num = data.get('spectro_num', self.spectro_num)
            
            if zeroline_data is None or baseline_data is None:
                print("✗ 校准文件中缺少零位或基线数据")
                return False
            
            if len(zeroline_data) != 2048 or len(baseline_data) != 2048:
                print(f"✗ 数据长度错误: 零位={len(zeroline_data)}, 基线={len(baseline_data)}, 期望2048")
                return False
            
            self.zeroline = (c_float * 2048)(*zeroline_data)
            self.baseline = (c_float * 2048)(*baseline_data)
            self.spectro_num = spectro_num
            
            # 尝试将校准数据写入DLL内部状态
            try:
                res_zero = self.pDll.JF_USB_SetZerolineMux(spectro_num, self.zeroline)
                res_base = self.pDll.JF_USB_SetBaselineMux(spectro_num, self.baseline)
                print(f"✓ 校准数据已写入DLL (零位返回:{res_zero}, 基线返回:{res_base})")
            except Exception as e:
                print(f"提示: DLL无设置函数({e}),校准数据仅在Python侧加载")
            
            timestamp = data.get('timestamp')
            if timestamp:
                import datetime
                ts_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                print(f"✓ 校准数据加载成功 (采集时间: {ts_str})")
            else:
                print("✓ 校准数据加载成功")
            return True
        
        except FileNotFoundError:
            print(f"✗ 找不到校准文件: {filepath}")
            return False
        except Exception as e:
            print(f"✗ 加载校准文件失败: {e}")
            return False

    def save_calibration(self, filepath=None, spectro_num=None):
        """交互式重新标定：分步采集零位和基线，保存到 JSON 文件

        Args:
            filepath: 保存路径，默认使用脚本目录下的 calibration_data.json
            spectro_num: 光谱仪通道号，默认使用实例的 spectro_num

        Returns:
            bool: 保存是否成功
        """
        import datetime

        if spectro_num is None:
            spectro_num = self.spectro_num
        if filepath is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(script_dir, "calibration_data.json")

        print("\n========== 重新采集校准数据 ==========")

        # 步骤1: 零位（需遮住光源）
        print("\n步骤1: 采集零位数据")
        print("请遮住光源(暗光谱),然后按Enter键继续...")
        input()
        zeroline_list = self.get_zeroline(spectro_num)
        if self.zeroline is None:
            print("✗ 零位采集失败，中止保存")
            return False

        # 步骤2: 基线（移除遮光物，管路中只有溶剂）
        print("\n步骤2: 采集基线数据")
        print("请移除遮光物,确保管路中只有溶剂(无样品),然后按Enter键继续...")
        input()
        baseline_list = self.get_baseline(spectro_num)
        if self.baseline is None:
            print("✗ 基线采集失败，中止保存")
            return False

        calibration = {
            "zeroline": zeroline_list,
            "baseline": baseline_list,
            "spectro_num": spectro_num,
            "timestamp": time.time(),
        }

        try:
            with open(filepath, 'w') as f:
                json.dump(calibration, f)
            ts_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n✓ 校准数据已保存: {filepath}  ({ts_str})")
            return True
        except Exception as e:
            print(f"✗ 保存校准文件失败: {e}")
            return False

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
    
    def continuous_monitor_multi_wavelengths(self, wavelengths, interval_sec=1, duration_sec=None, spectro_num=None, calibration_file=None):
        """连续监测多个波长的吸光度
        
        若未提前调用 calibrate() 或 get_zeroline()/get_baseline(),
        将自动从 calibration_file (默认 calibration_data.json) 加载已保存的校准数据。
        
        Args:
            wavelengths: 波长列表,单位nm
            interval_sec: 采样间隔,单位秒
            duration_sec: 监测时长,单位秒(None表示无限监测,按Ctrl+C停止)
            spectro_num: 光谱仪通道号,默认使用实例的spectro_num
            calibration_file: 校准数据文件路径,默认使用脚本目录下的 calibration_data.json
            
        Returns:
            list: [(时间戳, {波长: 吸光度}), ...]
        """
        if self.zeroline is None or self.baseline is None:
            print("未发现内存中的校准数据,尝试从文件加载...")
            if not self.load_calibration(calibration_file):
                print("错误: 校准数据加载失败,请先调用 calibrate() 或确保校准文件存在")
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


    def start(self, wavelengths="[280, 300, 400]", duration_sec=60.0, interval_sec=0.5, string="") -> dict:
        """UniLab 云端入口：连续监测多波长吸光度

        自动从 calibration_data.json 加载已保存的零位和基线，无需重新校准。
        当 280nm 吸光度落入 [-0.3, -0.1] 区间时，监测自动停止。

        Args:
            wavelengths: 波长列表，JSON 字符串格式，如 "[280, 300, 400]"，单位 nm
            duration_sec: 监测总时长，单位秒（传 0 或 null 表示无限监测）
            interval_sec: 采样间隔，单位秒
            string: 可选，JSON 字符串格式的全参数输入，如果提供则优先解析

        Returns:
            dict: {"return_info": str, "success": bool}
        """
        # 280nm 停止条件范围
        STOP_WAVE = 280.0
        STOP_LOW  = -0.9
        STOP_HIGH = -0.1

        try:
            if string:
                try:
                    params = json.loads(string)
                    wavelengths = params.get("wavelengths", wavelengths)
                    duration_sec = params.get("duration_sec", duration_sec)
                    interval_sec = params.get("interval_sec", interval_sec)
                except Exception:
                    pass

            if isinstance(wavelengths, str):
                wavelengths = json.loads(wavelengths)
            wavelengths = [float(w) for w in wavelengths]

            interval_sec = float(interval_sec) if interval_sec is not None else 0.5
            if duration_sec is None or str(duration_sec) in ("0", "0.0", "null", "None", ""):
                duration_sec = None
            else:
                duration_sec = float(duration_sec)

            # 确保校准数据已加载
            if self.zeroline is None or self.baseline is None:
                if not self.load_calibration():
                    return {"return_info": "监测失败：校准数据加载失败，请检查 calibration_data.json", "success": False}

            spectro_num = self.spectro_num

            print(f"\n========== 开始连续监测 ==========")
            print(f"监测波长: {wavelengths} nm")
            print(f"采样间隔: {interval_sec}秒")
            print(f"停止条件: {STOP_WAVE}nm 吸光度进入 [{STOP_LOW}, {STOP_HIGH}] 时自动停止")
            if duration_sec:
                print(f"最长监测时长: {duration_sec}秒")
            else:
                print("最长监测时长: 无限(按Ctrl+C停止)")
            print("-" * 80)

            header = f"{'时间(秒)':<12}"
            for wl in wavelengths:
                header += f"{wl}nm{'':<10}"
            print(header)
            print("-" * 80)

            data_records = []
            stop_reason = "达到最长监测时长"
            start_time = time.time()

            try:
                while True:
                    current_time = time.time() - start_time
                    abs_values = self.measure_absorbance_at_wavelengths(wavelengths, spectro_num, verbose=False)

                    if abs_values:
                        data_records.append((current_time, abs_values))

                        line = f"{current_time:<12.1f}"
                        for wl in wavelengths:
                            line += f"{abs_values.get(wl, 0):<14.4f}"
                        print(line)

                        # 280nm 停止条件检查
                        abs_280 = abs_values.get(STOP_WAVE)
                        if abs_280 is not None and STOP_LOW <= abs_280 <= STOP_HIGH:
                            stop_reason = f"280nm 吸光度 ({abs_280:.4f}) 进入停止区间 [{STOP_LOW}, {STOP_HIGH}]"
                            break

                    if duration_sec and current_time >= duration_sec:
                        break

                    time.sleep(interval_sec)

            except KeyboardInterrupt:
                stop_reason = "手动停止"

            print("=" * 80)
            print(f"监测结束：{stop_reason}")
            print(f"共采集 {len(data_records)} 个数据点")

            summary_lines = [
                f"监测完成，共采集 {len(data_records)} 个数据点，波长: {wavelengths} nm",
                f"停止原因: {stop_reason}",
            ]
            if data_records:
                last_t, last_abs = data_records[-1]
                abs_str = "  ".join(f"{wl}nm={v:.4f}" for wl, v in last_abs.items())
                summary_lines.append(f"最后一次读数 (t={last_t:.1f}s): {abs_str}")

            return {"return_info": "\n".join(summary_lines), "success": True}

        except Exception as e:
            return {"return_info": f"监测失败: {str(e)}", "success": False}


# 使用示例
if __name__ == "__main__":
    # 创建光谱仪实例
    spectrometer = JingfeiSpectrometer()
    
    # 设置积分时间
    spectrometer.set_integration_time(100)

    # ── 可选：重新采集零位和基线并覆盖 calibration_data.json ──
    # 遮住光源后再运行，或注释掉此段直接使用已有校准数据
    print("\n是否重新标定？(y=重新采集并保存 / 其他键=使用已有校准数据)")
    choice = input().strip().lower()
    if choice == 'y':
        spectrometer.save_calibration()

    # ── 连续监测（自动加载 calibration_data.json，280nm 进入 [-0.3,-0.1] 时自动停止）──
    result = spectrometer.start(
        wavelengths="[280, 300, 400]",
        interval_sec=0.5,
        duration_sec=0      # 0 表示无限监测，用 Ctrl+C 或停止条件结束
    )
    print(result["return_info"])

