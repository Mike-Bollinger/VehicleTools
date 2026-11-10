"""Tkinter entry point for the SeaTrac navigation bridge."""

from datetime import datetime, timezone
import glob
from pathlib import Path
import queue
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from serial.tools import list_ports

from bridge import BridgeWorker, Config


BAUD_RATES = ('4800', '9600', '19200', '38400', '57600', '115200', '230400')


class BridgeApp:
    def __init__(self, root):
        self.root = root
        self.worker = None
        self.was_running = False
        self.closing = False
        self.close_started = None
        self.config_widgets = []
        self.values = {}
        self.root.title('SeaTrac Navigation Bridge')
        self.root.geometry('1160x790')
        self.root.minsize(820, 660)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(3, weight=1)
        style = ttk.Style(root)
        style.configure('Start.TButton', font=('TkDefaultFont', 12, 'bold'), padding=(18, 8))

        header = ttk.Frame(root, padding=12)
        header.grid(row=0, column=0, sticky='ew')
        header.columnconfigure(1, weight=1)
        header.columnconfigure(3, weight=1)
        ttk.Label(header, text='GPS serial').grid(row=0, column=0, sticky='w', padx=(0, 8))
        self.gps_port = self.entry(header, 'gps_port', '', 0, 1, combo=True)
        ttk.Label(header, text='Baud').grid(row=0, column=2, padx=8)
        self.entry(header, 'gps_baud', '4800', 0, 3, combo=True, choices=BAUD_RATES, width=10)
        ttk.Label(header, text='Stop bits').grid(row=0, column=4, padx=8)
        self.entry(header, 'gps_stopbits', '1', 0, 5, combo=True, choices=('1', '2'), width=5)
        ttk.Label(header, text='SeaTrac serial').grid(row=1, column=0, sticky='w', padx=(0, 8))
        self.usbl_port = self.entry(header, 'usbl_port', '', 1, 1, combo=True)
        ttk.Label(header, text='Baud').grid(row=1, column=2, padx=8)
        self.entry(header, 'usbl_baud', '115200', 1, 3, combo=True, choices=BAUD_RATES, width=10)
        ttk.Label(header, text='8N2').grid(row=1, column=4, columnspan=2)
        refresh = ttk.Button(header, text='Refresh Ports', command=self.refresh_ports)
        refresh.grid(row=0, column=6, rowspan=2, padx=(12, 0), sticky='ns')
        self.config_widgets.append(refresh)

        options = ttk.Frame(root, padding=(12, 0, 12, 8))
        options.grid(row=1, column=0, sticky='ew')
        for column in (1, 3, 5, 7):
            options.columnconfigure(column, weight=1)
        fields = (
            ('UDP IPv4', 'udp_host', '127.0.0.1'), ('UDP port', 'udp_port', '27000'),
            ('ROV ID', 'target_id', '2'), ('Max input age (s)', 'max_age', '3'),
            ('Ping interval (s)', 'ping_interval', '2'), ('Reply timeout (s)', 'reply_timeout', '10'),
            ('Mount yaw (deg)', 'mounting_yaw', '0'), ('Surface MSL (m)', 'surface_msl', '0'),
            ('GPS to head forward (m)', 'lever_forward', '0'),
            ('GPS to head starboard (m)', 'lever_starboard', '0'),
        )
        for index, (label, name, default) in enumerate(fields):
            row, pair = divmod(index, 4)
            column = pair * 2
            ttk.Label(options, text=label).grid(row=row, column=column, sticky='w', padx=(0, 6), pady=4)
            self.entry(options, name, default, row, column + 1, width=12)
        self.values['active_ping'] = tk.BooleanVar(value=True)
        self.values['enhanced_ping'] = tk.BooleanVar(value=True)
        for column, (text, name) in enumerate((('Send pings', 'active_ping'),
                                               ('Enhanced depth', 'enhanced_ping'))):
            widget = ttk.Checkbutton(options, text=text, variable=self.values[name])
            widget.grid(row=2, column=4 + column * 2, columnspan=2, sticky='w', padx=8)
            self.config_widgets.append(widget)
        ttk.Label(options, text='Log directory').grid(row=3, column=0, sticky='w', pady=8)
        self.entry(options, 'log_directory', str(Path(__file__).resolve().parent / 'logs'),
                   3, 1, columnspan=6)
        browse = ttk.Button(options, text='Browse...', command=self.choose_directory)
        browse.grid(row=3, column=7, sticky='ew', padx=4)
        self.config_widgets.append(browse)

        controls = ttk.Frame(root, padding=(12, 0, 12, 10))
        controls.grid(row=2, column=0, sticky='ew')
        controls.columnconfigure(2, weight=1)
        self.start_button = ttk.Button(controls, text='Start', style='Start.TButton', command=self.start)
        self.start_button.grid(row=0, column=0, rowspan=2, padx=(0, 8), sticky='ns')
        self.stop_button = ttk.Button(controls, text='Stop', command=self.stop, state='disabled')
        self.stop_button.grid(row=0, column=1, rowspan=2, padx=(0, 12), sticky='ns')
        self.status = tk.StringVar(value='Stopped')
        self.position = tk.StringVar(value='No position transmitted')
        ttk.Label(controls, textvariable=self.status, wraplength=650).grid(row=0, column=2, sticky='w')
        ttk.Label(controls, textvariable=self.position, wraplength=650).grid(row=1, column=2, sticky='w')
        self.follow = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text='Follow feeds', variable=self.follow).grid(row=0, column=3, sticky='e')
        ttk.Button(controls, text='Clear Feeds', command=self.clear_feeds).grid(row=1, column=3, sticky='e')

        panes = ttk.Panedwindow(root, orient='horizontal')
        panes.grid(row=3, column=0, sticky='nsew', padx=12)
        self.feeds = {}
        for source, title in (('GPS', 'GPS / True Heading - Raw Input'),
                              ('USBL', 'SeaTrac - Raw Input / Ping Commands')):
            frame = ttk.Frame(panes)
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight=1)
            ttk.Label(frame, text=title, padding=(0, 4)).grid(row=0, column=0, sticky='w')
            text = tk.Text(frame, wrap='none', height=14, width=40, state='disabled',
                           font=('TkFixedFont', 10), background='#f6f8fa', foreground='#17212b')
            text.grid(row=1, column=0, sticky='nsew')
            vertical = ttk.Scrollbar(frame, orient='vertical', command=text.yview)
            vertical.grid(row=1, column=1, sticky='ns')
            horizontal = ttk.Scrollbar(frame, orient='horizontal', command=text.xview)
            horizontal.grid(row=2, column=0, sticky='ew')
            text.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
            self.feeds[source] = text
            panes.add(frame, weight=1)
        self.log_status = tk.StringVar(value='No log file yet')
        ttk.Label(root, textvariable=self.log_status, padding=12, wraplength=1000).grid(
            row=4, column=0, sticky='ew')
        self.refresh_ports()
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.poll_id = root.after(100, self.poll)

    def entry(self, parent, name, default, row, column, combo=False, choices=(), width=24, columnspan=1):
        variable = tk.StringVar(value=default)
        self.values[name] = variable
        if combo:
            widget = ttk.Combobox(parent, textvariable=variable, values=choices, width=width)
        else:
            widget = ttk.Entry(parent, textvariable=variable, width=width)
        widget.grid(row=row, column=column, columnspan=columnspan, sticky='ew', padx=4, pady=4)
        self.config_widgets.append(widget)
        return widget

    def refresh_ports(self):
        try:
            ports = sorted(set(glob.glob('/dev/serial/by-id/*') +
                               [port.device for port in list_ports.comports()]))
        except OSError as error:
            messagebox.showerror('Serial ports', str(error), parent=self.root)
            return
        self.gps_port.configure(values=ports)
        self.usbl_port.configure(values=ports)

    def choose_directory(self):
        selected = filedialog.askdirectory(parent=self.root, title='Navigation log directory')
        if selected:
            self.values['log_directory'].set(selected)

    def configuration(self):
        integers = {'gps_baud', 'usbl_baud', 'gps_stopbits', 'target_id', 'udp_port'}
        numbers = {'ping_interval', 'reply_timeout', 'max_age', 'mounting_yaw',
                   'lever_forward', 'lever_starboard', 'surface_msl'}
        values = {}
        for name, variable in self.values.items():
            value = variable.get()
            if name in integers:
                try:
                    value = int(value)
                except ValueError as error:
                    raise ValueError(f'{name} must be an integer.') from error
            elif name in numbers:
                try:
                    value = float(value)
                except ValueError as error:
                    raise ValueError(f'{name} must be a number.') from error
            elif isinstance(value, str):
                value = value.strip()
            values[name] = value
        config = Config(**values)
        config.validate()
        return config

    def start(self):
        pressed_at = datetime.now(timezone.utc)
        if self.worker is not None and self.worker.is_alive():
            return
        try:
            config = self.configuration()
            self.worker = BridgeWorker(config, pressed_at)
            self.worker.start()
        except (ValueError, OSError, RuntimeError) as error:
            messagebox.showerror('Cannot start bridge', str(error), parent=self.root)
            return
        self.was_running = True
        self.clear_feeds()
        self.position.set('No position transmitted')
        self.status.set('Opening connections...')
        self.log_status.set('Creating log...')
        self.start_button.state(['disabled'])
        self.stop_button.state(['!disabled'])
        for widget in self.config_widgets:
            widget.state(['disabled'])

    def stop(self):
        if self.worker is not None:
            self.worker.stop()
            self.status.set('Stopping...')
            self.stop_button.state(['disabled'])

    def clear_feeds(self):
        for text in self.feeds.values():
            text.configure(state='normal')
            text.delete('1.0', 'end')
            text.configure(state='disabled')

    def append(self, source, value):
        text = self.feeds[source]
        text.configure(state='normal')
        text.insert('end', value)
        line_count = int(text.index('end-1c').split('.')[0])
        if line_count > 2000:
            text.delete('1.0', f'{line_count - 1500}.0')
        if self.follow.get():
            text.see('end')
        text.configure(state='disabled')

    def poll(self):
        if self.worker is not None:
            batch = {'GPS': [], 'USBL': []}
            for _ in range(500):
                try:
                    source, value = self.worker.display.get_nowait()
                except queue.Empty:
                    break
                batch[source].append(value)
            for source, values in batch.items():
                if values:
                    self.append(source, ''.join(values))
            details = self.worker.snapshot()
            running = self.worker.is_alive()
            self.status.set('Stopping...' if running and self.worker.stop_requested.is_set()
                            else details['status'])
            if details['last_output'] is not None:
                age = time.monotonic() - details['last_output']
                validity = 'STALE' if age > self.worker.config.max_age or not running else 'Last sent'
                self.position.set(f"{validity}: {details['solution']} | {age:.1f} s ago | "
                                  f"UDP sent: {details['sent']}")
            if details['log']:
                self.log_status.set(f"Log: {details['log']} | Display-only lines dropped: "
                                    f"{details['display_dropped']}")
            if self.was_running and not running:
                self.was_running = False
                self.start_button.state(['!disabled'])
                self.stop_button.state(['disabled'])
                for widget in self.config_widgets:
                    widget.state(['!disabled'])
                if details['error'] and not self.closing:
                    messagebox.showerror('Bridge stopped', details['error'], parent=self.root)
        if self.closing:
            if self.worker is None or not self.worker.is_alive():
                self.root.destroy()
                return
            if time.monotonic() - self.close_started > 6:
                if messagebox.askyesno('Connections still closing',
                                      'Force quit? The final log rows may not be saved.', parent=self.root):
                    self.root.destroy()
                    return
                self.close_started = time.monotonic()
        self.poll_id = self.root.after(100, self.poll)

    def close(self):
        if self.closing:
            return
        if self.worker is not None and self.worker.is_alive():
            if not messagebox.askyesno('Stop bridge', 'Stop navigation output and close?', parent=self.root):
                return
        self.closing = True
        self.close_started = time.monotonic()
        self.start_button.state(['disabled'])
        self.stop()


def main():
    root = tk.Tk()
    BridgeApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()