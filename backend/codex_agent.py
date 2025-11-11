#!/usr/bin/env python3
"""
CompliancePulse Compliance Scanner
Works across all platforms: macOS, Linux, Windows WSL
"""
import json
import os
import subprocess
import sys
import platform
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import logging

# Setup logging
log_dir = os.getenv("LOGS_DIR", "/var/log")
log_file = os.path.join(log_dir, "compliancepulse-scan.log")

# Ensure log directory exists
Path(log_file).parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def run_command(cmd_list: list, timeout: int = 30) -> str:
    """Execute command safely with timeout"""
    try:
        result = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out: {' '.join(cmd_list)}")
        return "ERROR: Command timed out"
    except Exception as e:
        logger.error(f"Command failed: {' '.join(cmd_list)} - {e}")
        return f"ERROR: {str(e)}"

def sanitize_sensitive_data(data: str) -> str:
    """Remove or redact sensitive information"""
    sensitive_patterns = ['password', 'secret', 'key', 'token']
    lines = data.split('\n')
    sanitized = []
    
    for line in lines:
        lower_line = line.lower()
        if any(pattern in lower_line for pattern in sensitive_patterns):
            sanitized.append("[REDACTED - Sensitive Data]")
        else:
            sanitized.append(line)
    
    return '\n'.join(sanitized)

def collect_system_data() -> Dict[str, Any]:
    """Collect system compliance data (cross-platform)"""
    logger.info("Collecting system data...")
    
    data = {
        "timestamp": datetime.utcnow().isoformat(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "hostname": run_command(["hostname"]),
        "python_version": platform.python_version(),
    }
    
    # Platform-specific commands
    system = platform.system()
    
    if system == "Darwin":  # macOS
        data["uptime"] = run_command(["uptime"])
        data["disk_usage"] = run_command(["df", "-h"])
        data["memory"] = run_command(["vm_stat"])
    elif system == "Linux":
        if os.path.exists("/etc/os-release"):
            data["os_info"] = run_command(["cat", "/etc/os-release"])
        data["kernel"] = run_command(["uname", "-r"])
        data["uptime"] = run_command(["uptime"])
        data["disk_usage"] = run_command(["df", "-h"])
        if os.path.exists("/proc/meminfo"):
            data["memory"] = run_command(["cat", "/proc/meminfo"])
        try:
            data["failed_services"] = run_command(["systemctl", "list-units", "--type=service", "--state=failed", "--no-pager"])
        except:
            data["failed_services"] = "systemctl not available"
    elif system == "Windows":
        data["os_version"] = run_command(["cmd", "/c", "systeminfo"])
        data["disk_usage"] = run_command(["cmd", "/c", "wmic logicaldisk get name,size,freespace"])
    
    logger.info("System data collection complete")
    return data

def analyze_with_openai(data: Dict[str, Any]) -> str:
    """Send data to OpenAI for analysis"""
    try:
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set - skipping AI analysis")
            return "AI analysis skipped: API key not configured"
        
        client = OpenAI(api_key=api_key)
        
        prompt = f"""Analyze this system compliance snapshot and provide:
1. System health assessment
2. Any security considerations
3. Configuration recommendations
4. Overall status

System Data:
{json.dumps(data, indent=2)}

Provide a concise, structured analysis."""
        
        logger.info("Requesting analysis from OpenAI...")
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a system compliance auditor."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        analysis = response.choices[0].message.content
        logger.info("OpenAI analysis complete")
        return analysis
        
    except ImportError:
        logger.warning("OpenAI package not installed")
        return "AI analysis not available: OpenAI package not installed"
    except Exception as e:
        logger.warning(f"OpenAI API error: {e}")
        return f"AI analysis failed: {str(e)}"

def generate_report(system_data: Dict[str, Any], analysis: str) -> Dict[str, Any]:
    """Generate final compliance report"""
    return {
        "metadata": {
            "timestamp": system_data["timestamp"],
            "hostname": system_data["hostname"],
            "platform": system_data.get("platform", "unknown"),
            "scanner_version": "0.3.0"
        },
        "system_data": system_data,
        "analysis": analysis,
        "summary": {
            "total_checks": 5,
            "status": "completed"
        }
    }

def save_report(report: Dict[str, Any], data_dir: Path):
    """Save report with timestamp and maintain latest"""
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Save timestamped version
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        timestamped_path = data_dir / f"compliance_report_{timestamp}.json"
        
        with open(timestamped_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Update latest report
        latest_path = data_dir / "compliance_report.json"
        with open(latest_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved: {timestamped_path}")
        
        # Cleanup old reports (keep last 30)
        cleanup_old_reports(data_dir, keep=30)
        
    except Exception as e:
        logger.error(f"Failed to save report: {e}")
        raise

def cleanup_old_reports(data_dir: Path, keep: int = 30):
    """Remove old timestamped reports"""
    try:
        reports = sorted(data_dir.glob("compliance_report_*.json"))
        if len(reports) > keep:
            for old_report in reports[:-keep]:
                old_report.unlink()
                logger.info(f"Removed old report: {old_report.name}")
    except Exception as e:
        logger.warning(f"Cleanup failed: {e}")

def main():
    """Main execution"""
    logger.info("=" * 60)
    logger.info("CompliancePulse Compliance Scan Started")
    logger.info("=" * 60)
    
    base_dir = os.getenv("BASE_DIR", "/opt/compliancepulse")
    data_dir = Path(base_dir) / "data"
    
    try:
        # Collect data
        system_data = collect_system_data()
        
        # Analyze with AI
        analysis = analyze_with_openai(system_data)
        
        # Generate report
        report = generate_report(system_data, analysis)
        
        # Save report
        save_report(report, data_dir)
        
        logger.info("=" * 60)
        logger.info("✅ Compliance scan completed successfully")
        logger.info("=" * 60)
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Scan failed: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
