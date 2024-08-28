import pandas as pd
import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from tkinter import Tk, filedialog, Label, Button, OptionMenu, StringVar


# Function to load CSV
def load_csv():
    root = Tk()
    root.withdraw()  # Hide the root window
    file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
    if file_path:
        return pd.read_csv(file_path, delimiter=';')
    else:
        return None


# Function to filter and convert data
def process_data(data):
    # Define the epoch time for January 1, 2024
    epoch_2024 = 1704067200

    # Filter the data to include only timestamps greater than the epoch time for 2024
    filtered_data = data[data['timestamp s'] > epoch_2024]

    # Convert timestamp to a more readable format
    filtered_data['timestamp s'] = pd.to_datetime(filtered_data['timestamp s'], unit='s')

    # Convert Pitch, Roll, and Heading from radians to degrees
    filtered_data['Pitch deg'] = np.degrees(filtered_data['Pitch rad'])
    filtered_data['Roll deg'] = np.degrees(filtered_data['Roll rad'])
    filtered_data['Heading deg'] = np.degrees(filtered_data['Heading rad'])

    # Convert Speed from m/s to knots
    filtered_data['Speed knots'] = filtered_data['Speed m/s'] * 1.94384

    # Convert Depth to Negative
    filtered_data['Water Depth m'] = (filtered_data['Depth m'] + filtered_data['Bottom m']) * -1
    filtered_data['Depth m'] = filtered_data['Depth m'] * -1
    filtered_data['Altitude m'] = filtered_data['Bottom m']

    return filtered_data


# Function to create interactive plot
def create_plot(data, y1_attr, y2_attr, y3_attr, y4_attr):
    fig = go.Figure()

    # Add traces for each selected attribute
    fig.add_trace(
        go.Scatter(x=data['timestamp s'], y=data[y1_attr], mode='lines', name=y1_attr)
    )
    fig.add_trace(
        go.Scatter(x=data['timestamp s'], y=data[y2_attr], mode='lines', name=y2_attr)
    )
    fig.add_trace(
        go.Scatter(x=data['timestamp s'], y=data[y3_attr], mode='lines', name=y3_attr)
    )
    fig.add_trace(
        go.Scatter(x=data['timestamp s'], y=data[y4_attr], mode='lines', name=y4_attr)
    )

    # Update layout for zoom and inspection
    fig.update_layout(
        title=f'{y1_attr}, {y2_attr}, {y3_attr}, and {y4_attr} Over Time',
        xaxis_title='Time',
        yaxis_title='Value',
        hovermode='x unified',
    )

    # Show the plot
    fig.show()



# Main function to run the program
def main():
    data = load_csv()
    if data is not None:
        filtered_data = process_data(data)

        # Create GUI for selecting attributes
        root = Tk()
        root.title("Select Attributes for Plotting")
        # Increase window size
        root.geometry('200x300')  # Set width x height

        # Dropdown for first attribute
        y1_var = StringVar(root)
        y1_var.set('Depth m')  # default value
        y1_label = Label(root, text="Y1 Attribute:")
        y1_label.pack()
        y1_menu = OptionMenu(root, y1_var, *filtered_data.columns)
        y1_menu.pack()

        # Dropdown for second attribute
        y2_var = StringVar(root)
        y2_var.set('Altitude m')  # default value
        y2_label = Label(root, text="Y2 Attribute:")
        y2_label.pack()
        y2_menu = OptionMenu(root, y2_var, *filtered_data.columns)
        y2_menu.pack()

        # Dropdown for third attribute
        y3_var = StringVar(root)
        y3_var.set('Water Depth m')  # default value
        y3_label = Label(root, text="Y3 Attribute:")
        y3_label.pack()
        y3_menu = OptionMenu(root, y3_var, *filtered_data.columns)
        y3_menu.pack()

        # Dropdown for fourth attribute
        y4_var = StringVar(root)
        y4_var.set('Pitch deg')  # default value
        y4_label = Label(root, text="Y4 Attribute:")
        y4_label.pack()
        y4_menu = OptionMenu(root, y4_var, *filtered_data.columns)
        y4_menu.pack()

        # Button to update plot
        def update_plot():
            create_plot(filtered_data, y1_var.get(), y2_var.get(), y3_var.get(), y4_var.get())

        plot_button = Button(root, text="Update Plot", command=update_plot)
        plot_button.pack()

        root.mainloop()
    else:
        print("No file selected or invalid file.")


if __name__ == "__main__":
    main()
