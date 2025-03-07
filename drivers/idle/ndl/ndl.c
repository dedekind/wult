// SPDX-License-Identifier: GPL-2.0-only
/*
 * Copyright (C) 2019-2021 Intel Corporation
 * Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>
 */

#include <linux/debugfs.h>
#include <linux/err.h>
#include <linux/fs.h>
#include <linux/module.h>
#include <linux/netdevice.h>
#include <linux/pci.h>
#include <linux/string.h>

#define DRIVER_NAME "ndl"
#define NDL_VERSION "1.0"

#define I210_RR2DCDELAY 0x5BF4
#define I210_RR2DCDELAY_INCR 16

/* Name of the network device to attach to. */
static char *ifname;

/* The network device corresponding to the 'ifname' interface. */
static struct net_device *i210_ndev;

/* The PCI device corresponding to the 'ifname' interface. */
static struct pci_dev *i210_pdev;

/* The network device IO memory base address. */
static u8 __iomem *i210_iomem;

/* Driver's root debugfs directory. */
static struct dentry *dfsroot;

static ssize_t dfs_read_file(struct file *file, char __user *user_buf,
			     size_t count, loff_t *ppos)
{
	ssize_t res;
	u64 rtd;
	char buf[64];
	struct dentry *dent = file->f_path.dentry;

	res = debugfs_file_get(dent);
	if (res)
		return res;

	rtd = readl(&i210_iomem[I210_RR2DCDELAY]);
	rtd *= I210_RR2DCDELAY_INCR;
	snprintf(buf, sizeof(buf), "%llu", rtd);
	debugfs_file_put(dent);

	return simple_read_from_buffer(user_buf, count, ppos, buf, strlen(buf));
}

static const struct file_operations dfs_ops = {
	.read = dfs_read_file,
	.open = simple_open,
	.llseek = default_llseek,
};

static int dfs_create(void)
{
	struct dentry *dent;

	dfsroot = debugfs_create_dir(DRIVER_NAME, NULL);
	if (IS_ERR(dfsroot))
		return PTR_ERR(dfsroot);

	dent = debugfs_create_file("rtd", 0444, dfsroot, NULL, &dfs_ops);
	if (IS_ERR(dent)) {
		debugfs_remove(dfsroot);
		return PTR_ERR(dfsroot);
	}

	return 0;
}

/* Find the PCI device for a network device. */
static struct pci_dev * __init find_pci_device(const struct net_device *ndev)
{
	struct pci_dev *pdev = NULL;

	while ((pdev = pci_get_device(PCI_VENDOR_ID_INTEL, PCI_ANY_ID, pdev))
	       != NULL) {
		if (!pdev->driver || strcmp(pdev->driver->name, "igb"))
			/* I210 devices are managed by the 'igb' driver. */
			continue;
		if (pdev->dev.driver_data == ndev)
			break;
	}

	return pdev;
}

static int ndl_do_init(void)
{
	int err;

	if (i210_ndev)
		return NOTIFY_DONE;

	i210_ndev = dev_get_by_name(&init_net, ifname);
	if (!i210_ndev) {
		pr_err(DRIVER_NAME ": network device '%s' was not found\n",
		       ifname);
		return -EINVAL;
	}

	i210_pdev = find_pci_device(i210_ndev);
	if (!i210_pdev) {
		pr_err(DRIVER_NAME ": cannot find PCI device for network device '%s'\n",
		       i210_ndev->name);
		err = -EINVAL;
		goto error_put_ndev;
	}

	/* Get the base IO memory address. */
	i210_iomem = pci_iomap(i210_pdev, 0, 0);

	err = dfs_create();
	if (err)
		goto error_put_pdev;

	return 0;

error_put_pdev:
	pci_dev_put(i210_pdev);
	pci_iounmap(i210_pdev, i210_iomem);
error_put_ndev:
	dev_put(i210_ndev);
	i210_ndev = NULL;

	return err;
}

static void ndl_do_exit(void)
{
	dev_put(i210_ndev);
	i210_ndev = NULL;
	pci_dev_put(i210_pdev);
	pci_iounmap(i210_pdev, i210_iomem);
	debugfs_remove_recursive(dfsroot);
}

static int ndl_netdevice_event(struct notifier_block *notifier,
			       unsigned long event, void *ptr)
{
	struct net_device *dev = netdev_notifier_info_to_dev(ptr);
	int err;

	if (dev != i210_ndev)
		return NOTIFY_DONE;

	switch (event) {
	case NETDEV_REGISTER:
		err = ndl_do_init();
		if (err)
			pr_err(DRIVER_NAME ": ndl init failed:%d\n", err);
		break;
	case NETDEV_UNREGISTER:
		ndl_do_exit();
		break;
	default:
		break;
	};

	return NOTIFY_DONE;
}

static struct notifier_block ndl_netdevice_notifier = {
	.notifier_call = ndl_netdevice_event,
};

/* Module initialization function. */
static int __init ndl_init(void)
{
	int err;

	if (!ifname) {
		pr_err(DRIVER_NAME ": network interface name not specified\n");
		return -EINVAL;
	}

	err = ndl_do_init();
	if (err)
		return err;

	err = register_netdevice_notifier(&ndl_netdevice_notifier);
	if (err) {
		pr_err(DRIVER_NAME ": failed to register notifier\n");
		ndl_do_exit();
	}

	return err;
}
module_init(ndl_init);

/* Module exit function. */
static void __exit ndl_exit(void)
{
	unregister_netdevice_notifier(&ndl_netdevice_notifier);

	if (!i210_ndev)
		return;

	ndl_do_exit();
}
module_exit(ndl_exit);

module_param(ifname, charp, 0644);
MODULE_PARM_DESC(ifname, "name of the network interface to use.");

MODULE_VERSION(NDL_VERSION);
MODULE_DESCRIPTION("the ndl driver.");
MODULE_AUTHOR("Artem Bityutskiy");
MODULE_LICENSE("GPL v2");
