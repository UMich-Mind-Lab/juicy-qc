var qc = [];
var qcval = 0;
var flagval = 0;

var i = 0;
var l = 0;

document.addEventListener('keydown', function(event) {
    if (event.keyCode == 83) {
	resetViewer();
    } else if (event.keyCode == 32) {
	qc[i] = [papayaContainers[0].viewer.screenVolumes[1].volume.fileName,0,0,username,checktype];
	i = Math.max(0,i-1);
	resetViewer();
    } else if (event.keyCode == 37) {
	qc[i] = [papayaContainers[0].viewer.screenVolumes[1].volume.fileName,0,0,username,checktype];
	i = Math.min(l,i+1);
	resetViewer();
    } else if (event.keyCode == 39) {
	qc[i] = [papayaContainers[0].viewer.screenVolumes[1].volume.fileName,1,0,username,checktype];
	i = Math.min(l,i+1);
	resetViewer();
    } else if (event.keyCode == 70) {
	qc[i] = [papayaContainers[0].viewer.screenVolumes[1].volume.fileName,0,1,username,checktype];
	i = Math.min(l,i+1);
	resetViewer();
    }
});

function resetViewer() {
    fetch("images.json")
	.then(response => response.json())
	.then((data) => {
	    params["smoothDisplay"] = false;
	    params["images"] = data[i];
	    l = data.length;
	    func = data[i][1].substring(data[i][1].lastIndexOf("/")+1);
	    console.log(func);
	    document.getElementById("subject").innerHTML = data[i][1];
	    params[func] = {"minPercent": 0.1, "maxPercent":1,"lut": "Red Overlay","alpha":0.65,"interpolation":false};
	    papaya.Container.resetViewer(0,params);
	});
}

function SaveCSV() {
    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "FuncImage,RegOK,Flag,rater,check\n";
    qc.forEach(function(rowArray) {
	let row = rowArray.join(",");
	csvContent += row + "\n";
    });
    var encodedUri = encodeURI(csvContent);
    var link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", tempname + ".csv");
    document.body.appendChild(link); // Required for FF

    link.click(); // This will download the data file named "my_data.csv".
}
